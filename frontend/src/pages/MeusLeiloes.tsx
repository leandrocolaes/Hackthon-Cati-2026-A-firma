// Leilões do usuário em qualquer estado (cancelados e encerrados somem do catálogo,
// mas continuam aqui), com editar/cancelar quando o servidor permite.
import { useCallback, useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { AcoesDoComitente } from "../components/AcoesDoComitente";
import { FotoLeilao } from "../components/FotoLeilao";
import { SeloEstado } from "../components/SeloEstado";
import { api, NOME_DO_ESTADO, type ErroApi, type MeuLeilaoApi } from "../lib/api";
import { useAuth } from "../lib/auth";
import { formatarBRL, formatarDataHora } from "../lib/format";

export function MeusLeiloes() {
  const { usuario, carregando } = useAuth();
  const [itens, setItens] = useState<MeuLeilaoApi[] | null>(null);
  const [erro, setErro] = useState("");

  const carregar = useCallback(() => {
    api.get<{ itens: MeuLeilaoApi[] }>("/api/meus-leiloes")
      .then((r) => { setItens(r.itens); setErro(""); })
      .catch((e: ErroApi) => setErro(e.message));
  }, []);

  useEffect(() => {
    if (!usuario) return;
    carregar();
    const t = window.setInterval(carregar, 15_000); // estados mudam sozinhos (abertura/fechamento)
    return () => window.clearInterval(t);
  }, [usuario, carregar]);

  if (!carregando && !usuario) return <Navigate to="/entrar?voltar=/meus-leiloes" replace />;

  return (
    <main className="detalhe">
      <p className="etiqueta">Comitente</p>
      <h1>Meus leilões</h1>
      {erro && <p className="aviso-sala" role="alert">{erro}</p>}
      {itens === null ? (
        !erro && <p className="detalhe__legenda">Carregando…</p>
      ) : itens.length === 0 ? (
        <p className="detalhe__legenda">
          Você ainda não anunciou nada. <Link to="/anunciar">Anunciar um item</Link>
        </p>
      ) : (
        <ul className="meus">
          {itens.map((l) => (
            <li key={l.id} className="meus__item">
              <Link to={`/leiloes/${l.id}`} className="meus__foto">
                <FotoLeilao nome={l.nome} categoria={l.categoria} fotos={l.foto_principal ? [l.foto_principal] : []} />
              </Link>
              <div className="meus__info">
                <div className="detalhe__topo">
                  <Link to={`/leiloes/${l.id}`}><strong>{l.nome}</strong></Link>
                  <SeloEstado estado={NOME_DO_ESTADO[l.estado] ?? "Agendado"} />
                </div>
                <p className="detalhe__legenda">
                  {l.total_lances > 0 ? `Lance atual ${formatarBRL(l.preco_atual)}` : `Preço inicial ${formatarBRL(l.preco_inicial)}`}
                  {" · "}Início {formatarDataHora(l.inicio)}
                  {" · "}{l.total_lances} lance(s){" · "}{l.participantes} na sala
                </p>
                <AcoesDoComitente leilao={l} aoMudar={carregar} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
