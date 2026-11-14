import { useEffect, useRef, useState } from "react";

// Página de teste das conexões. Não tem funcionalidade do leilão ainda.
export default function App() {
  // 1) HTTP: React → Nginx → FastAPI → PostgreSQL
  const [health, setHealth] = useState<unknown>("carregando...");

  useEffect(() => {
    fetch("/api/health") // caminho relativo: o Nginx (ou o Vite em dev) encaminha
      .then((r) => r.json())
      .then(setHealth)
      .catch((e) => setHealth(`erro: ${e}`));
  }, []);

  // 2) WebSocket: conexão aberta, servidor responde na hora
  const wsRef = useRef<WebSocket | null>(null);
  const [wsStatus, setWsStatus] = useState("desconectado");
  const [mensagens, setMensagens] = useState<string[]>([]);

  useEffect(() => {
    const protocolo = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${protocolo}://${location.host}/api/ws`);
    ws.onopen = () => setWsStatus("conectado");
    ws.onclose = () => setWsStatus("desconectado");
    ws.onmessage = (e) => setMensagens((m) => [...m, e.data]);
    wsRef.current = ws;
    return () => ws.close();
  }, []);

  return (
    <main style={{ fontFamily: "sans-serif", padding: 24 }}>
      <h1>Teste de conexões</h1>

      <h2>HTTP → /api/health</h2>
      <pre>{JSON.stringify(health, null, 2)}</pre>

      <h2>WebSocket → /api/ws ({wsStatus})</h2>
      <button onClick={() => wsRef.current?.send("olá")}>Enviar "olá"</button>
      <pre>{mensagens.join("\n")}</pre>
    </main>
  );
}
