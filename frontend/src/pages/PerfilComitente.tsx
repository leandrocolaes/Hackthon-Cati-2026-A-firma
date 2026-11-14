// Perfil público do comitente (RF22): nome de exibição, leilões ativos e resumo dos
// encerrados. A API não devolve e-mail nem ids internos; a URL usa a referência pública.
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { CartaoLeilao } from "../components/CartaoLeilao";
import { SeloEstado } from "../components/SeloEstado";
import { api, leilaoDoCartao, NOME_DO_ESTADO, type CartaoApi, type ErroApi } from "../lib/api";
import { formatarDataHora } from "../lib/format";
import { useRelogio } from "../lib/useRelogio";

interface PerfilApi {
  ref: string;
  nome: string;
  ativos: CartaoApi[];
  encerrados: {
    vendidos: number;
    sem_lances: number;
    cancelados: number;
    recentes: { id: number; nome: string; categoria: string; estado: string; encerrado_em: string }[];
  };
}

export function PerfilComitente() {
  const { ref } = useParams();
  const agora = useRelogio();
  const [perfil, setPerfil] = useState<PerfilApi | null>(null);
  const [situacao, setSituacao] = useState<"carregando" | "ok" | "nao_encontrado" | "erro">("carregando");

  useEffect(() => {
    setSituacao("carregando");
    api.get<PerfilApi>(`/api/comitentes/${encodeURIComponent(ref ?? "")}`)
      .then((p) => { setPerfil(p); setSituacao("ok"); })
      .catch((e: ErroApi) => setSituacao(e.status === 404 ? "nao_encontrado" : "erro"));
  }, [ref]);

  if (situacao === "carregando") return <main className="detalhe"><p className="detalhe__legenda">Carregando…</p></main>;
  if (situacao !== "ok" || !perfil) {
    return (
      <main className="detalhe">
        <p className="aviso-sala" role="alert">
          {situacao === "nao_encontrado" ? "Comitente não encontrado." : "Não foi possível carregar o perfil."}
        </p>
        <Link className="voltar" to="/">← Voltar para o catálogo</Link>
      </main>
    );
  }

  const { encerrados } = perfil;
  return (
    <main className="detalhe">
      <Link className="voltar" to="/">← Voltar para o catálogo</Link>
      <p className="etiqueta">Comitente</p>
      <h1>{perfil.nome}</h1>

      <h2 className="sala__titulo">Leilões em andamento e agendados</h2>
      {perfil.ativos.length === 0 ? (
        <p className="detalhe__legenda">Nenhum leilão ativo no momento.</p>
      ) : (
        <div className="grade">
          {perfil.ativos.map((c) => <CartaoLeilao key={c.id} leilao={leilaoDoCartao(c)} agora={agora} />)}
        </div>
      )}

      <h2 className="sala__titulo">Encerrados</h2>
      <p className="detalhe__legenda">
        {encerrados.vendidos} vendido(s) · {encerrados.sem_lances} sem lances · {encerrados.cancelados} cancelado(s)
      </p>
      {encerrados.recentes.length > 0 && (
        <ul className="meus">
          {encerrados.recentes.map((l) => (
            <li key={l.id} className="meus__item">
              <div className="meus__info">
                <div className="detalhe__topo">
                  <Link to={`/leiloes/${l.id}`}><strong>{l.nome}</strong></Link>
                  <SeloEstado estado={NOME_DO_ESTADO[l.estado] ?? "Cancelado"} />
                </div>
                <p className="detalhe__legenda">{l.categoria} · encerrado em {formatarDataHora(l.encerrado_em)}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
