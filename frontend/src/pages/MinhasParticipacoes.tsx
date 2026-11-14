// Minhas participações (RF27): leilões em que entrei na sala, em quatro grupos.
// O servidor decide o grupo de cada leilão; a tela só agrupa e dá o atalho certo:
// sala (?sala=1) enquanto a disputa está ativa, senão o detalhe.
import { useCallback, useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { FotoLeilao } from "../components/FotoLeilao";
import { SeloEstado } from "../components/SeloEstado";
import { api, NOME_DO_ESTADO, type ErroApi } from "../lib/api";
import { useAuth } from "../lib/auth";
import { formatarBRL, formatarDataHora } from "../lib/format";

interface ParticipacaoApi {
  id: number;
  nome: string;
  categoria: string;
  foto_principal: string | null;
  estado: string;
  preco: string;
  termino: string;
  sala_acessivel: boolean;
}

type Grupos = Record<"em_disputa" | "vencidos" | "nao_vencidos" | "cancelados_encerrados", ParticipacaoApi[]>;

const TITULOS: { chave: keyof Grupos; titulo: string; vazio: string }[] = [
  { chave: "em_disputa", titulo: "Em disputa", vazio: "Nenhuma disputa agendada ou em andamento." },
  { chave: "vencidos", titulo: "Vencidos", vazio: "Você ainda não venceu nenhum leilão." },
  { chave: "nao_vencidos", titulo: "Não vencidos", vazio: "Nada por aqui." },
  { chave: "cancelados_encerrados", titulo: "Cancelados/encerrados", vazio: "Nada por aqui." },
];

export function MinhasParticipacoes() {
  const { usuario, carregando } = useAuth();
  const [grupos, setGrupos] = useState<Grupos | null>(null);
  const [erro, setErro] = useState("");

  const carregar = useCallback(() => {
    api.get<Grupos>("/api/minhas-participacoes")
      .then((g) => { setGrupos(g); setErro(""); })
      .catch((e: ErroApi) => setErro(e.message));
  }, []);

  useEffect(() => {
    if (!usuario) return;
    carregar();
    const t = window.setInterval(carregar, 15_000); // disputas abrem e fecham sozinhas
    return () => window.clearInterval(t);
  }, [usuario, carregar]);

  if (!carregando && !usuario) return <Navigate to="/entrar?voltar=/minhas-participacoes" replace />;

  return (
    <main className="detalhe">
      <p className="etiqueta">Participante</p>
      <h1>Minhas participações</h1>
      {erro && <p className="aviso-sala" role="alert">{erro}</p>}
      {grupos === null ? (
        !erro && <p className="detalhe__legenda">Carregando…</p>
      ) : (
        TITULOS.map(({ chave, titulo, vazio }) => (
          <section key={chave}>
            <h2 className="sala__titulo">{titulo} ({grupos[chave].length})</h2>
            {grupos[chave].length === 0 ? (
              <p className="detalhe__legenda">{vazio}</p>
            ) : (
              <ul className="meus">
                {grupos[chave].map((l) => {
                  const destino = l.sala_acessivel ? `/leiloes/${l.id}?sala=1` : `/leiloes/${l.id}`;
                  const ativo = l.estado === "agendado" || l.estado === "em_andamento";
                  return (
                    <li key={l.id} className="meus__item">
                      <Link to={destino} className="meus__foto">
                        <FotoLeilao nome={l.nome} categoria={l.categoria}
                          fotos={l.foto_principal ? [l.foto_principal] : []} />
                      </Link>
                      <div className="meus__info">
                        <div className="detalhe__topo">
                          <Link to={destino}><strong>{l.nome}</strong></Link>
                          <SeloEstado estado={NOME_DO_ESTADO[l.estado] ?? "Agendado"} />
                        </div>
                        <p className="detalhe__legenda">
                          {ativo ? "Preço atual" : "Preço final"} {formatarBRL(l.preco)}
                          {" · "}{ativo ? "Término" : "Encerrado em"} {formatarDataHora(l.termino)}
                        </p>
                        <Link to={destino}>{l.sala_acessivel ? "Ir para a sala →" : "Ver detalhe →"}</Link>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        ))
      )}
    </main>
  );
}
