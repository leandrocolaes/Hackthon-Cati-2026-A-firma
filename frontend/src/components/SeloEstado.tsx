import type { EstadoLeilao } from "../classes/Leilao";

const modificadores: Record<EstadoLeilao, string> = {
  Agendado: "agendado",
  "Em andamento": "andamento",
  Vendido: "vendido",
  "Encerrado sem lances": "encerrado",
  Cancelado: "cancelado",
};

export function SeloEstado({ estado }: { estado: EstadoLeilao }) {
  return <span className={`selo selo--${modificadores[estado]}`}>{estado}</span>;
}
