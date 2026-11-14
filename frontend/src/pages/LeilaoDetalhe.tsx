import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { FotoLeilao } from "../components/FotoLeilao";
import { SeloEstado } from "../components/SeloEstado";
import { leiloesDemonstracao } from "../lib/dados-demo";
import { formatarBRL, formatarDataHora } from "../lib/format";
import { useRelogio } from "../lib/useRelogio";

export function LeilaoDetalhe() {
  const { id } = useParams();
  const agora = useRelogio();
  const [avisoSala, setAvisoSala] = useState(false);

  const leilao = leiloesDemonstracao.find(
    (candidato) => candidato.id === Number(id),
  );

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
            fotos={leilao.item.fotos}
            grande
          />
          <p className="detalhe__legenda">
            Imagem ilustrativa. As fotos reais do item serão exibidas quando o
            anúncio for criado pelo fluxo de cadastro.
          </p>
        </div>

        <article className="detalhe__painel">
          <div className="detalhe__topo">
            <p className="detalhe__categoria">{leilao.item.categoria}</p>
            <SeloEstado estado={leilao.estado} />
          </div>

          <h1>{leilao.item.nome}</h1>
          <p className="detalhe__descricao">{leilao.item.descricao}</p>

          <div className="detalhe__preco">
            <span>{leilao.rotuloPreco}</span>
            <strong>{formatarBRL(leilao.precoEmDestaque)}</strong>
            <small>{leilao.tempoEmDestaque(agora)}</small>
          </div>

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

          <button
            type="button"
            className="botao botao--principal botao--largo"
            onClick={() => setAvisoSala(true)}
          >
            Entrar na sala
          </button>

          {avisoSala && (
            <p className="aviso-sala" role="status">
              A entrada na sala exige login. O fluxo de autenticação será
              conectado na etapa F03; até lá, o acompanhamento ao vivo não está
              disponível.
            </p>
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
