const formatoInteiro = new Intl.NumberFormat("pt-BR", {
  maximumFractionDigits: 0,
});

const formatoDataHora = new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "short",
  timeStyle: "short",
});

/**
 * Formata um valor decimal em reais sem converter para ponto flutuante.
 * Contratos da API usam strings decimais, por exemplo "120.50".
 */
export function formatarBRL(valor: string): string {
  const normalizado = valor.trim();
  if (!/^\d+(\.\d{1,2})?$/.test(normalizado)) {
    return "R$ --";
  }

  const [inteiro, decimal = ""] = normalizado.split(".");
  const centavos = `${decimal}00`.slice(0, 2);
  return `R$ ${formatoInteiro.format(BigInt(inteiro))},${centavos}`;
}

/** Exibe o instante no fuso do navegador, como exige o RF19. */
export function formatarDataHora(iso: string): string {
  return formatoDataHora.format(new Date(iso));
}

const formatoHora = new Intl.DateTimeFormat("pt-BR", { timeStyle: "medium" });

/** Só o horário com segundos (hard end da sala: o segundo importa). */
export function formatarHora(iso: string): string {
  return formatoHora.format(new Date(iso));
}

export function formatarDuracao(milissegundos: number): string {
  if (milissegundos <= 0) {
    return "agora";
  }

  const totalMinutos = Math.ceil(milissegundos / 60_000);
  const dias = Math.floor(totalMinutos / 1_440);
  const horas = Math.floor((totalMinutos % 1_440) / 60);
  const minutos = totalMinutos % 60;

  if (dias > 0) {
    return `${dias}d ${horas}h`;
  }
  if (horas > 0) {
    return `${horas}h ${minutos}min`;
  }
  return `${minutos}min`;
}
