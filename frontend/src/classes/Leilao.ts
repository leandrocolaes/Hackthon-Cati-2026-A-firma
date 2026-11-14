import { formatarDataHora, formatarDuracao } from "../lib/format";

export type EstadoLeilao =
  | "Agendado"
  | "Em andamento"
  | "Vendido"
  | "Encerrado sem lances"
  | "Cancelado";

export interface ItemDoLeilao {
  nome: string;
  descricao: string;
  categoria: string;
  fotos: string[];
}

/** Formato público acordado para o catálogo (F05). */
export interface DadosDoLeilao {
  id: number;
  item: ItemDoLeilao;
  estado: EstadoLeilao;
  precoInicial: string;
  precoAtual: string;
  lanceMinimo: string;
  inicio: string;
  terminoOriginal: string;
  terminoVigente: string;
  totalLances: number;
  lider: string | null;
}

/**
 * Representa um leilão no frontend.
 *
 * Valores de dinheiro permanecem como strings decimais, iguais às recebidas da
 * API. O frontend nunca recalcula lances: apenas exibe o que o servidor enviou.
 */
export class Leilao {
  readonly id: number;
  readonly item: ItemDoLeilao;
  readonly estado: EstadoLeilao;
  readonly precoInicial: string;
  readonly precoAtual: string;
  readonly lanceMinimo: string;
  readonly inicio: string;
  readonly terminoOriginal: string;
  readonly terminoVigente: string;
  readonly totalLances: number;
  readonly lider: string | null;

  constructor(dados: DadosDoLeilao) {
    this.id = dados.id;
    this.item = dados.item;
    this.estado = dados.estado;
    this.precoInicial = dados.precoInicial;
    this.precoAtual = dados.precoAtual;
    this.lanceMinimo = dados.lanceMinimo;
    this.inicio = dados.inicio;
    this.terminoOriginal = dados.terminoOriginal;
    this.terminoVigente = dados.terminoVigente;
    this.totalLances = dados.totalLances;
    this.lider = dados.lider;
  }

  get emAndamento(): boolean {
    return this.estado === "Em andamento";
  }

  get agendado(): boolean {
    return this.estado === "Agendado";
  }

  get apareceNoCatalogo(): boolean {
    return this.emAndamento || this.agendado;
  }

  get precoEmDestaque(): string {
    return this.emAndamento ? this.precoAtual : this.precoInicial;
  }

  get rotuloPreco(): string {
    return this.emAndamento ? "Lance atual" : "Preço inicial";
  }

  get dataEmDestaque(): string {
    return this.emAndamento ? this.terminoVigente : this.inicio;
  }

  get rotuloData(): string {
    return this.emAndamento ? "Termina" : "Começa";
  }

  get horarioEmDestaqueFormatado(): string {
    return formatarDataHora(this.dataEmDestaque);
  }

  tempoEmDestaque(agora: Date = new Date()): string {
    const diferenca = new Date(this.dataEmDestaque).getTime() - agora.getTime();
    if (diferenca <= 0) {
      return this.emAndamento ? "Encerrando..." : "Começando...";
    }
    const prefixo = this.emAndamento ? "Termina em" : "Começa em";
    return `${prefixo} ${formatarDuracao(diferenca)}`;
  }

  /** RF20: em andamento pelo término mais próximo, depois agendados pelo início. */
  static compararParaCatalogo(a: Leilao, b: Leilao): number {
    if (a.emAndamento !== b.emAndamento) {
      return a.emAndamento ? -1 : 1;
    }

    const dataA = new Date(a.dataEmDestaque).getTime();
    const dataB = new Date(b.dataEmDestaque).getTime();
    if (dataA !== dataB) {
      return dataA - dataB;
    }
    return a.id - b.id;
  }

  static catalogo(leiloes: Leilao[]): Leilao[] {
    return leiloes
      .filter((leilao) => leilao.apareceNoCatalogo)
      .sort(Leilao.compararParaCatalogo);
  }
}
