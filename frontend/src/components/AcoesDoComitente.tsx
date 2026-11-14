// Editar e cancelar, só para o comitente. Os botões aparecem quando o servidor diz que
// pode (GET /api/meus-leiloes); ao receber o pedido, o servidor confere de novo.
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, type ErroApi, type MeuLeilaoApi } from "../lib/api";

export function AcoesDoComitente({ leilao, aoMudar }: { leilao: MeuLeilaoApi; aoMudar: () => void }) {
  const [erro, setErro] = useState("");
  const [cancelando, setCancelando] = useState(false);

  async function cancelar() {
    if (!window.confirm(`Cancelar "${leilao.nome}"? Não dá para desfazer.`)) return;
    setErro("");
    setCancelando(true);
    try {
      await api.post(`/api/leiloes/${leilao.id}/cancelar`);
      aoMudar();
    } catch (e) {
      setErro((e as ErroApi).message);
      aoMudar(); // o estado pode ter mudado (ex.: alguém deu lance): atualiza os botões
    } finally {
      setCancelando(false);
    }
  }

  if (!leilao.pode_editar && !leilao.pode_cancelar) return null;
  return (
    <div className="acoes-comitente">
      {leilao.pode_editar && (
        <Link className="botao botao--dourado" to={`/leiloes/${leilao.id}/editar`}>Editar</Link>
      )}
      {leilao.pode_cancelar && (
        <button type="button" className="botao-link" onClick={cancelar} disabled={cancelando}>
          {cancelando ? "Cancelando…" : "Cancelar leilão"}
        </button>
      )}
      {erro && <p className="aviso-sala" role="alert">{erro}</p>}
    </div>
  );
}
