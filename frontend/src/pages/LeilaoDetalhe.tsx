import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import type { Leilao } from "../classes/Leilao";
import { FotoLeilao } from "../components/FotoLeilao";
import { SalaAoVivo } from "../components/SalaAoVivo";
import { SeloEstado } from "../components/SeloEstado";
import { api, ErroApi, leilaoDoDetalhe, type DetalheApi } from "../lib/api";
import { useAuth } from "../lib/auth";
import { formatarBRL, formatarDataHora } from "../lib/format";
import { useRelogio } from "../lib/useRelogio";

export function LeilaoDetalhe() {
  const { id } = useParams();
  const agora = useRelogio();
  const [naSala, setNaSala] = useState(false);
  const [fotoAtual, setFotoAtual] = useState(0);
  const { usuario } = useAuth();
  const navegar = useNavigate();
  const local = useLocation();
  const [leilao, setLeilao] = useState<Leilao | null>(null);
  const [situacao, setSituacao] = useState<"carregando" | "ok" | "nao_encontrado" | "erro">("carregando");

  useEffect(() => {
    setSituacao("carregando");
    api.get<DetalheApi>(`/api/leiloes/${id}`)
      .then((d) => { setLeilao(leilaoDoDetalhe(d)); setSituacao("ok"); })
      .catch((e: ErroApi) => setSituacao(e.status === 404 ? "nao_encontrado" : "erro"));
  }, [id]);

  function entrarNaSala() {
    if (!usuario) {
      // A sala exige login: vai para o login e volta para cá depois.
      navegar(`/entrar?voltar=${encodeURIComponent(local.pathname)}`);
      return;
    }
    setNaSala(true);
  }

  if (situacao === "carregando") {
    return <main className="detalhe"><p className="detalhe__legenda">Carregando…</p></main>;
  }

  if (situacao === "erro") {
    return (
      <main className="detalhe">
        <p className="aviso-sala" role="alert">Não foi possível carregar o leilão. Tente de novo.</p>
      </main>
    );
  }

  if (!leilao) {
    return (
      <main className="detalhe">
        <div className="nao-encontrado">
          <p className="etiqueta">Leilão não encontrado</p>
          <h1>Este anúncio não existe ou não está disponível.</h1>
          <p>
            Confira o endereço acessado ou volte ao catálogo para escolher outro
            leilão.
          </p>
          <Link className="botao botao--principal" to="/">
            Ver catálogo
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="detalhe">
      <Link className="voltar" to="/">
        ← Voltar para o catálogo
      </Link>

      <div className="detalhe__grade">
        <div className="detalhe__midia">
          <FotoLeilao
            nome={leilao.item.nome}
            categoria={leilao.item.categoria}
            fotos={leilao.item.fotos.slice(fotoAtual).concat(leilao.item.fotos).slice(0, 1)}
            grande
          />
          {leilao.item.fotos.length > 1 && (
            <div className="miniaturas">
              {leilao.item.fotos.map((url, i) => (
                <button key={url} type="button" onClick={() => setFotoAtual(i)}
                  className={`miniaturas__item${i === fotoAtual ? " ativo" : ""}`}
                  aria-label={`Ver foto ${i + 1}`}>
                  <img src={url} alt="" loading="lazy" />
                </button>
              ))}
            </div>
          )}
        </div>

        <article className="detalhe__painel">
          <div className="detalhe__topo">
            <p className="detalhe__categoria">{leilao.item.categoria}</p>
            <SeloEstado estado={leilao.estado} />
          </div>

          <h1>{leilao.item.nome}</h1>
          <p className="detalhe__descricao">{leilao.item.descricao}</p>

          {/* Com a sala aberta, o preço ao vivo fica na sala (este seria o da hora do carregamento). */}
          {!naSala && (
            <div className="detalhe__preco">
              <span>{leilao.rotuloPreco}</span>
              <strong>{formatarBRL(leilao.precoEmDestaque)}</strong>
              <small>{leilao.tempoEmDestaque(agora)}</small>
            </div>
          )}

          <dl className="detalhe__dados">
            <div>
              <dt>Início</dt>
              <dd>{formatarDataHora(leilao.inicio)}</dd>
            </div>
            <div>
              <dt>Término vigente</dt>
              <dd>{formatarDataHora(leilao.terminoVigente)}</dd>
            </div>
            <div>
              <dt>Categoria</dt>
              <dd>{leilao.item.categoria}</dd>
            </div>
            <div>
              <dt>Estado</dt>
              <dd>{leilao.estado}</dd>
            </div>
          </dl>

          {naSala && usuario ? (
            <SalaAoVivo leilaoId={leilao.id} />
          ) : (
            <button
              type="button"
              className="botao botao--principal botao--largo"
              onClick={entrarNaSala}
            >
              Entrar na sala
            </button>
          )}

          <p className="detalhe__rodape">
            O detalhe público apresenta o item e o anúncio. Lances, histórico e
            identificação do líder ficam restritos à sala autenticada.
          </p>
        </article>
      </div>
    </main>
  );
}
