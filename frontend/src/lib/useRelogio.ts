import { useEffect, useState } from "react";

/** Mantém contadores e horários atualizados sem recarregar a página. */
export function useRelogio(intervaloMs = 30_000): Date {
  const [agora, setAgora] = useState(() => new Date());

  useEffect(() => {
    const identificador = window.setInterval(() => setAgora(new Date()), intervaloMs);
    return () => window.clearInterval(identificador);
  }, [intervaloMs]);

  return agora;
}
