// Ligação do frontend com a API do backend (contrato em docs/contratos.md).
//
// - Caminhos sempre RELATIVOS (/api/...): o Nginx (VM) ou o Vite (dev) encaminham.
// - O cookie de sessão vai sozinho (mesma origem); o JavaScript nem consegue lê-lo.
// - Erros da API chegam como {codigo, mensagem, detalhes} e viram ErroApi.
import type { DadosDoLeilao, EstadoLeilao } from "../classes/Leilao";
import { Leilao } from "../classes/Leilao";

export class ErroApi extends Error {
  constructor(
    public status: number, // 0 = sem resposta (rede caiu)
    public codigo: string,
    mensagem: string,
    public detalhes: Record<string, unknown> = {},
    public corpo: unknown = null,
  ) {
    super(mensagem);
  }
}

async function pedir<T>(caminho: string, opcoes: RequestInit = {}): Promise<T> {
  let resposta: Response;
  try {
    resposta = await fetch(caminho, opcoes);
  } catch {
    throw new ErroApi(0, "sem_conexao", "Sem conexão com o servidor.");
  }
  if (resposta.status === 204) return undefined as T;
  const corpo = await resposta.json().catch(() => null);
  if (!resposta.ok) {
    const campos = corpo?.detalhes?.campos as { motivo: string }[] | undefined;
    const mensagem = campos?.length ? campos.map((c) => c.motivo).join(" ") : corpo?.mensagem;
    throw new ErroApi(resposta.status, corpo?.codigo ?? "erro", mensagem ?? "Erro inesperado.",
      corpo?.detalhes ?? {}, corpo);
  }
  return corpo as T;
}

export const api = {
  get: <T>(caminho: string) => pedir<T>(caminho),
  post: <T>(caminho: string, dados?: unknown) =>
    pedir<T>(caminho, {
      method: "POST",
      headers: dados === undefined ? {} : { "Content-Type": "application/json" },
      body: dados === undefined ? undefined : JSON.stringify(dados),
    }),
  put: <T>(caminho: string, dados: unknown) =>
    pedir<T>(caminho, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(dados) }),
  delete: <T>(caminho: string) => pedir<T>(caminho, { method: "DELETE" }),
  // multipart: o navegador define o Content-Type com o boundary sozinho.
  enviarArquivo: <T>(caminho: string, campo: string, arquivo: File) => {
    const corpo = new FormData();
    corpo.append(campo, arquivo);
    return pedir<T>(caminho, { method: "POST", body: corpo });
  },
};

// Chave única por tentativa de lance (RF12).
// crypto.randomUUID() só existe em contexto seguro (HTTPS ou localhost). Na VM o
// acesso é http://IP:porta, onde ele NÃO existe; getRandomValues funciona sempre.
export function novaChave(): string {
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40; // versão 4
  b[8] = (b[8] & 0x3f) | 0x80; // variante RFC 4122
  const h = Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

// ---------- tradução das respostas da API para a classe Leilao ----------

export const NOME_DO_ESTADO: Record<string, EstadoLeilao> = {
  agendado: "Agendado",
  em_andamento: "Em andamento",
  vendido: "Vendido",
  encerrado_sem_lances: "Encerrado sem lances",
  cancelado: "Cancelado",
};

export interface CartaoApi {
  id: number;
  nome: string;
  categoria: string;
  foto_principal: string | null;
  preco_atual: string;
  estado: string;
  inicio: string;
  termino_vigente: string;
}

export interface DetalheApi {
  id: number;
  item: { id: number; nome: string; descricao: string; categoria: string; fotos: { url: string; ordem: number }[] };
  comitente: { nome: string; ref: string }; // RF22: só o que é público
  estado: string;
  preco_inicial: string;
  preco_atual: string;
  inicio: string;
  termino_vigente: string;
  versao: number;
}

/** GET /api/meus-leiloes: o servidor diz o que o comitente ainda pode fazer. */
export interface MeuLeilaoApi {
  id: number;
  nome: string;
  categoria: string;
  foto_principal: string | null;
  estado: string;
  preco_inicial: string;
  preco_atual: string;
  inicio: string;
  termino_vigente: string;
  total_lances: number;
  participantes: number;
  versao: number; // RF23
  pode_editar: boolean;
  pode_cancelar: boolean;
}

/** Catálogo: só o necessário para o cartão (o catálogo não traz descrição nem lances). */
export function leilaoDoCartao(c: CartaoApi): Leilao {
  const dados: DadosDoLeilao = {
    id: c.id,
    item: { nome: c.nome, descricao: "", categoria: c.categoria, fotos: c.foto_principal ? [c.foto_principal] : [] },
    estado: NOME_DO_ESTADO[c.estado] ?? "Agendado",
    // Antes de abrir não há lances, então o preço atual é o inicial.
    precoInicial: c.preco_atual,
    precoAtual: c.preco_atual,
    lanceMinimo: c.preco_atual,
    inicio: c.inicio,
    terminoOriginal: c.termino_vigente,
    terminoVigente: c.termino_vigente,
    totalLances: 0,
    lider: null,
  };
  return new Leilao(dados);
}

/** Detalhe público: lances e líder ficam na sala (exige login). */
export function leilaoDoDetalhe(d: DetalheApi): Leilao {
  return new Leilao({
    id: d.id,
    item: {
      nome: d.item.nome,
      descricao: d.item.descricao,
      categoria: d.item.categoria,
      fotos: [...d.item.fotos].sort((a, b) => a.ordem - b.ordem).map((f) => f.url),
    },
    estado: NOME_DO_ESTADO[d.estado] ?? "Agendado",
    precoInicial: d.preco_inicial,
    precoAtual: d.preco_atual,
    lanceMinimo: d.preco_atual,
    inicio: d.inicio,
    terminoOriginal: d.termino_vigente,
    terminoVigente: d.termino_vigente,
    totalLances: 0,
    lider: null,
  });
}
