// Estado da sala ao vivo (RF09; docs/contratos.md, "Sala" e "WS").
//
// 1) Lê o snapshot (GET /sala). Só se o servidor responder 403 (ainda não participa)
//    entra na sala (POST /participantes). Assim recarregar a página ou reconectar não
//    chama POST de novo: não renova a sessão só por assistir (RF24, seção 2.1).
// 2) Abre o WebSocket, que manda o snapshot ao conectar e sempre que a versão do
//    leilão muda (lance, abertura, fechamento, cancelamento, edição).
// 3) Se o WebSocket cair, reconecta sozinho; ao reabrir, o primeiro snapshot já é o
//    estado confirmado atual. Enquanto isso, consulta por polling de reserva.
// 4) Snapshot com versão MENOR que a já exibida é descartado (nunca volta no tempo).
// 5) Fechamento 4401 = sessão expirada: avisa o login.
// Modo espectador (RF25): sem login e sem participação. Lê GET /espectador e abre o WS
// com ?modo=espectador; recebe o snapshot público (só apelidos) até o resultado.
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ErroApi } from "./api";

export interface Pessoa {
  participante_id?: number; // ausente no snapshot público do espectador
  apelido: string;
}

export type ModoSala = "participante" | "espectador";

export interface Snapshot {
  id: number;
  versao: number;
  estado: string;
  server_time: string;
  inicio: string;
  termino_original: string;
  termino_vigente: string;
  hard_end: string; // RF15: término original + 10 min (teto das prorrogações)
  prorrogacao_esgotada: boolean;
  preco_atual: string;
  lance_minimo: string;
  lider: Pessoa | null;
  total_lances: number;
  ultimos_lances: (Pessoa & { id?: number; valor: string; criado_em: string })[];
  resultado: { vencedor: Pessoa; valor: string } | null;
  // Só no snapshot do participante (o do espectador não tem nada pessoal):
  meu_participante_id?: number;
  sou_comitente?: boolean;
  pode_dar_lance?: boolean;
  motivo_impedimento?: string | null;
  espectador?: boolean;
}

// DECISAO: reconexão e polling de reserva a cada 2 s.
const RECONECTAR_MS = 2000;
const RESERVA_MS = 2000;

export function useSala(leilaoId: number, ativa: boolean, aoExpirar: () => void,
  modo: ModoSala = "participante") {
  const espectador = modo === "espectador";
  const caminhoSnapshot = `/api/leiloes/${leilaoId}/${espectador ? "espectador" : "sala"}`;
  const [sala, setSala] = useState<Snapshot | null>(null);
  const [erro, setErro] = useState("");
  const [aoVivo, setAoVivo] = useState(false);
  // RF26: o servidor manda "aviso": "lance_superado" no máximo uma vez por leilão.
  const [superado, setSuperado] = useState(false);
  // Relógio do servidor - relógio do navegador (ms): a contagem usa o do servidor (RF16).
  const [deslocamento, setDeslocamento] = useState(0);
  const versao = useRef(-1);

  // Só aceita snapshot igual ou mais novo: mensagens atrasadas não voltam a tela no tempo.
  const aplicar = useCallback((s: Snapshot) => {
    if (s.versao < versao.current) return;
    versao.current = s.versao;
    setDeslocamento(Date.parse(s.server_time) - Date.now());
    setSala(s);
  }, []);

  const recarregar = useCallback(() => {
    api.get<Snapshot>(caminhoSnapshot)
      .then((s) => { aplicar(s); setErro(""); })
      .catch((e: ErroApi) => {
        if (e.status === 401 && !espectador) aoExpirar();
        setErro(e.message);
      });
  }, [caminhoSnapshot, espectador, aplicar, aoExpirar]);

  useEffect(() => {
    if (!ativa) return;
    let encerrada = false;
    let ws: WebSocket | null = null;
    let reconexao: number | undefined;

    function conectar() {
      const protocolo = location.protocol === "https:" ? "wss" : "ws";
      const sufixo = espectador ? "?modo=espectador" : "";
      ws = new WebSocket(`${protocolo}://${location.host}/api/leiloes/${leilaoId}/ws${sufixo}`);
      ws.onopen = () => setAoVivo(true);
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        if (msg.tipo === "estado_leilao") aplicar(msg.estado);
        if (msg.aviso === "lance_superado") setSuperado(true);
      };
      ws.onclose = (e) => {
        setAoVivo(false);
        if (encerrada) return;
        if (e.code === 4401) { aoExpirar(); return; }
        if (e.code === 4409) { setErro("Só dá para assistir a leilões em andamento."); return; }
        reconexao = window.setTimeout(conectar, RECONECTAR_MS);
      };
    }

    const falhou = (e: ErroApi) => {
      if (e.status === 401) aoExpirar();
      setErro(e.message);
    };
    api.get<Snapshot>(caminhoSnapshot)
      .then((s) => { if (!encerrada) { aplicar(s); setErro(""); conectar(); } })
      .catch((e: ErroApi) => {
        if (espectador || e.status !== 403 || e.codigo !== "participante_ausente") return falhou(e);
        // Primeira entrada nesta sala: cria a participação (ação do usuário, renova a sessão).
        api.post(`/api/leiloes/${leilaoId}/participantes`)
          .then(() => { if (!encerrada) { recarregar(); conectar(); } })
          .catch(falhou);
      });
    // Polling de reserva: só consulta enquanto o WebSocket NÃO está aberto.
    const reserva = window.setInterval(() => {
      if (ws && ws.readyState !== WebSocket.OPEN) recarregar();
    }, RESERVA_MS);

    return () => {
      encerrada = true;
      window.clearInterval(reserva);
      window.clearTimeout(reconexao);
      ws?.close();
    };
  }, [ativa, leilaoId, espectador, caminhoSnapshot, recarregar, aplicar, aoExpirar]);

  const dispensarAviso = useCallback(() => setSuperado(false), []);
  return { sala, erro, aoVivo, deslocamento, recarregar, superado, dispensarAviso };
}
