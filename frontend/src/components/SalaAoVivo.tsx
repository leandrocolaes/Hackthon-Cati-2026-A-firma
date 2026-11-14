// Sala ao vivo: estado da disputa e lance (RF09-RF12, RF15, RF16). Editar/cancelar: AcoesDoComitente.
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ErroApi, NOME_DO_ESTADO, novaChave } from "../lib/api";
import { useAuth } from "../lib/auth";
import { formatarBRL, formatarDataHora, formatarHora } from "../lib/format";
import { useSala, type ModoSala, type Pessoa } from "../lib/useSala";
import { SeloEstado } from "./SeloEstado";

// DECISAO: textos para os códigos de impedimento do contrato.
const IMPEDIMENTOS: Record<string, string> = {
  leilao_fora_do_estado: "O leilão ainda não começou.",
  leilao_encerrado: "O leilão já terminou.",
  lance_do_comitente: "Você é o comitente: acompanha, mas não dá lances.",
  lance_do_lider: "Você é o líder. Espere outro lance para cobrir.",
};

function contagem(ms: number): string {
  if (ms <= 0) return "0s";
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), seg = s % 60;
  if (h > 0) return `${h}h ${m}min`;
  if (m > 0) return `${m}min ${String(seg).padStart(2, "0")}s`;
  return `${seg}s`;
}

export function SalaAoVivo({ leilaoId, aoAlterar, modo = "participante" }:
  { leilaoId: number; aoAlterar?: () => void; modo?: ModoSala }) {
  const { sessaoExpirou } = useAuth();
  const { sala, erro, aoVivo, deslocamento, recarregar } = useSala(leilaoId, true, sessaoExpirou, modo);
  const espectador = modo === "espectador";
  // Versão nova com o leilão ainda agendado = o comitente editou (nada mais muda a versão
  // antes da abertura). A página recarrega nome, fotos e descrição, e mostra um aviso.
  const anterior = useRef<{ versao: number; estado: string } | null>(null);
  const [editado, setEditado] = useState(false);
  useEffect(() => {
    if (!sala) return;
    const antes = anterior.current;
    anterior.current = { versao: sala.versao, estado: sala.estado };
    if (!antes || sala.versao <= antes.versao) return;
    if (antes.estado === "agendado" && sala.estado === "agendado") setEditado(true);
    if (sala.estado !== antes.estado || sala.estado === "agendado") aoAlterar?.();
  }, [sala, aoAlterar]);
  const [, setTique] = useState(0);
  useEffect(() => {
    const t = window.setInterval(() => setTique((x) => x + 1), 1000);
    return () => window.clearInterval(t);
  }, []);

  if (!sala) return <p className={erro ? "aviso-sala" : "detalhe__legenda"}>{erro || "Entrando na sala…"}</p>;

  // Espectador só vê apelidos; "Você" só existe para quem participa.
  const quem = (p: Pessoa | null) =>
    !p ? "—" : !espectador && p.participante_id === sala.meu_participante_id ? "Você" : p.apelido;
  const final = ["vendido", "encerrado_sem_lances", "cancelado"].includes(sala.estado);
  const alvo = sala.estado === "agendado" ? sala.inicio : sala.termino_vigente;
  const restante = Date.parse(alvo) - (Date.now() + deslocamento);

  return (
    <section className="sala" aria-label="Sala do leilão">
      <div className="detalhe__topo">
        <p className="detalhe__categoria">
          {espectador ? "Assistindo como espectador" : "Sala ao vivo"} {aoVivo ? "●" : "○ reconectando…"}
        </p>
        <SeloEstado estado={NOME_DO_ESTADO[sala.estado] ?? "Agendado"} />
      </div>

      {editado && sala.estado === "agendado" && (
        <p className="aviso-sala" role="status">
          O comitente alterou este anúncio. Confira os dados atualizados.{" "}
          <button type="button" className="botao-link" onClick={() => setEditado(false)}>OK</button>
        </p>
      )}

      {final ? (
        <div className="detalhe__preco">
          <span>Resultado</span>
          <strong>{sala.resultado ? formatarBRL(sala.resultado.valor) : NOME_DO_ESTADO[sala.estado]}</strong>
          {sala.resultado && <small>Vendido para {quem(sala.resultado.vencedor)}</small>}
        </div>
      ) : (
        <div className="detalhe__preco">
          <span>Lance atual</span>
          <strong>{formatarBRL(sala.preco_atual)}</strong>
          <small>
            {sala.estado === "agendado" ? "Começa em " : "Termina em "}
            {contagem(restante)}
            {sala.termino_vigente !== sala.termino_original && " (prorrogado)"}
          </small>
        </div>
      )}

      {/* RF15: enquanto ainda pode prorrogar, mostra o teto; no teto, aviso fixo. */}
      {sala.estado === "em_andamento" && (sala.prorrogacao_esgotada ? (
        <p className="aviso-sala aviso-sala--forte" role="status">
          Prorrogação máxima atingida: o leilão encerra definitivamente às {formatarHora(sala.hard_end)}.
          Novos lances não prorrogam mais.
        </p>
      ) : (
        <p className="detalhe__legenda">
          Lances no último minuto prorrogam o término, no máximo até {formatarHora(sala.hard_end)}.
        </p>
      ))}

      <dl className="detalhe__dados">
        <div><dt>Lance mínimo</dt><dd>{formatarBRL(sala.lance_minimo)}</dd></div>
        <div><dt>Líder</dt><dd>{quem(sala.lider)}</dd></div>
        <div><dt>Lances</dt><dd>{sala.total_lances}</dd></div>
        <div><dt>Término vigente</dt><dd>{formatarDataHora(sala.termino_vigente)}</dd></div>
      </dl>

      {/* RF25: espectador não recebe controles de lance nem menus de participante/comitente. */}
      {espectador ? (
        erro && <p className="aviso-sala">{erro}</p>
      ) : sala.pode_dar_lance ? (
        <FormLance leilaoId={leilaoId} minimo={sala.lance_minimo} aoMudar={recarregar} aoExpirar={sessaoExpirou} />
      ) : (
        !final && sala.motivo_impedimento && <p className="aviso-sala">{IMPEDIMENTOS[sala.motivo_impedimento]}</p>
      )}

      {/* Editar e cancelar ficam na página do leilão (AcoesDoComitente), fora da sala. */}

      <h3 className="sala__titulo">Últimos lances</h3>
      {sala.ultimos_lances.length === 0 ? (
        <p className="detalhe__legenda">Nenhum lance ainda.</p>
      ) : (
        <ol className="sala__lances">
          {sala.ultimos_lances.map((l, i) => (
            <li key={l.id ?? `${l.criado_em}-${i}`}>
              <span>{quem(l)}</span>
              <strong>{formatarBRL(l.valor)}</strong>
              <small>{formatarDataHora(l.criado_em)}</small>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function FormLance({ leilaoId, minimo, aoMudar, aoExpirar }:
  { leilaoId: number; minimo: string; aoMudar: () => void; aoExpirar: () => void }) {
  const [valor, setValor] = useState(minimo);
  const [mensagem, setMensagem] = useState<{ texto: string; ok: boolean } | null>(null);
  // Tentativa sem resposta (rede caiu): o reenvio usa a MESMA chave (RF12).
  const [pendente, setPendente] = useState<{ chave: string; valor: string } | null>(null);
  const [enviando, setEnviando] = useState(false);
  // RF13: depois de um 429, segura o botão até o servidor permitir de novo (quem decide
  // continua sendo o servidor; isto só evita cliques que seriam recusados).
  const [esperaAte, setEsperaAte] = useState(0);
  const [, setTique] = useState(0);
  const espera = Math.max(0, Math.ceil((esperaAte - Date.now()) / 1000));
  useEffect(() => {
    if (esperaAte <= Date.now()) return;
    const t = window.setInterval(() => setTique((x) => x + 1), 250);
    const fim = window.setTimeout(() => window.clearInterval(t), esperaAte - Date.now() + 300);
    return () => { window.clearInterval(t); window.clearTimeout(fim); };
  }, [esperaAte]);

  async function enviar(chave: string, v: string) {
    setEnviando(true);
    setMensagem(null);
    try {
      await api.post(`/api/leiloes/${leilaoId}/lances`, { valor: v.trim().replace(",", "."), chave });
      setPendente(null);
      setMensagem({ texto: "Lance aceito!", ok: true });
    } catch (e) {
      const erro = e as ErroApi;
      if (erro.status === 0) {
        setPendente({ chave, valor: v });
        setMensagem({ texto: "Sem resposta do servidor. Tente de novo: a mesma tentativa não é duplicada.", ok: false });
      } else if (erro.status === 429) {
        // Cedo demais: a tentativa não foi gravada; o mesmo valor pode ir de novo depois.
        const segundos = Number(erro.detalhes?.segundos_restantes ?? 2);
        setEsperaAte(Date.now() + segundos * 1000);
        setPendente(null);
        setMensagem({ texto: erro.message, ok: false });
      } else {
        setPendente(null);
        if (erro.status === 401) aoExpirar();
        const novoMinimo = erro.detalhes?.lance_minimo as string | undefined;
        setMensagem({ texto: erro.message + (novoMinimo ? ` Mínimo agora: ${formatarBRL(novoMinimo)}.` : ""), ok: false });
        if (novoMinimo) setValor(novoMinimo);
      }
    } finally {
      setEnviando(false);
      aoMudar();
    }
  }

  function aoEnviar(e: FormEvent) {
    e.preventDefault();
    enviar(novaChave(), valor); // chave nova a cada CLIQUE
  }

  return (
    <form className="sala__form" onSubmit={aoEnviar}>
      <label className="campo">
        Seu lance (mínimo {formatarBRL(minimo)})
        <input inputMode="decimal" value={valor} onChange={(e) => setValor(e.target.value)} />
      </label>
      <div className="sala__acoes">
        <button type="button" className="botao-link" onClick={() => setValor(minimo)}>Usar o mínimo</button>
        <button className="botao botao--principal" disabled={enviando || espera > 0}>
          {enviando ? "Enviando…" : espera > 0 ? `Aguarde ${espera} s` : "Dar lance"}
        </button>
      </div>
      {pendente && (
        <button type="button" className="botao botao--dourado botao--largo" disabled={enviando}
          onClick={() => enviar(pendente.chave, pendente.valor)}>
          Tentar de novo ({formatarBRL(pendente.valor.replace(",", "."))})
        </button>
      )}
      {mensagem && <p className={mensagem.ok ? "sala__ok" : "aviso-sala"} role="status">{mensagem.texto}</p>}
    </form>
  );
}
