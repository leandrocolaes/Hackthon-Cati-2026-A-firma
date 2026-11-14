// Estado da sala ao vivo (RF09; docs/contratos.md, "Sala" e "WS").
//
// 1) Entra na sala (POST /participantes: cria ou reaproveita a participação).
// 2) Lê o snapshot (GET /sala) e abre o WebSocket, que manda o snapshot sempre que a
//    versão do leilão muda (lance, abertura, fechamento, cancelamento).
// 3) Se o WebSocket cair, reconecta sozinho e, enquanto isso, consulta por polling.
// 4) Fechamento 4401 = sessão expirada: avisa o login.
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ErroApi } from "./api";

export interface Pessoa {
  participante_id: number;
  apelido: string;
}

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
  ultimos_lances: (Pessoa & { id: number; valor: string; criado_em: string })[];
  resultado: { vencedor: Pessoa; valor: string } | null;
  meu_participante_id: number;
  sou_comitente: boolean;
  pode_dar_lance: boolean;
  motivo_impedimento: string | null;
}

// DECISAO: reconexão e polling de reserva a cada 2 s.
const RECONECTAR_MS = 2000;
const RESERVA_MS = 2000;

export function useSala(leilaoId: number, ativa: boolean, aoExpirar: () => void) {
  const [sala, setSala] = useState<Snapshot | null>(null);
  const [erro, setErro] = useState("");
  const [aoVivo, setAoVivo] = useState(false);
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
    api.get<Snapshot>(`/api/leiloes/${leilaoId}/sala`)
      .then((s) => { aplicar(s); setErro(""); })
      .catch((e: ErroApi) => {
        if (e.status === 401) aoExpirar();
        setErro(e.message);
      });
  }, [leilaoId, aplicar, aoExpirar]);

  useEffect(() => {
    if (!ativa) return;
    let encerrada = false;
    let ws: WebSocket | null = null;
    let reconexao: number | undefined;

    function conectar() {
      const protocolo = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${protocolo}://${location.host}/api/leiloes/${leilaoId}/ws`);
      ws.onopen = () => setAoVivo(true);
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        if (msg.tipo === "estado_leilao") aplicar(msg.estado);
      };
      ws.onclose = (e) => {
        setAoVivo(false);
        if (encerrada) return;
        if (e.code === 4401) { aoExpirar(); return; }
        reconexao = window.setTimeout(conectar, RECONECTAR_MS);
      };
    }

    api.post(`/api/leiloes/${leilaoId}/participantes`)
      .then(() => { if (!encerrada) { recarregar(); conectar(); } })
      .catch((e: ErroApi) => {
        if (e.status === 401) aoExpirar();
        setErro(e.message);
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
  }, [ativa, leilaoId, recarregar, aplicar, aoExpirar]);

  return { sala, erro, aoVivo, deslocamento, recarregar };
}
