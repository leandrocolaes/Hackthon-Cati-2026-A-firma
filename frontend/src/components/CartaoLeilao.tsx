import { Link } from "react-router-dom";
import type { Leilao } from "../classes/Leilao";
import { formatarBRL } from "../lib/format";
import { FotoLeilao } from "./FotoLeilao";
import { SeloEstado } from "./SeloEstado";

interface CartaoLeilaoProps {
  leilao: Leilao;
  agora: Date;
}

export function CartaoLeilao({ leilao, agora }: CartaoLeilaoProps) {
  return (
    <article className="cartao">
      <Link
        className="cartao__link"
        to={`/leiloes/${leilao.id}`}
        aria-label={`Ver detalhes de ${leilao.item.nome}`}
      >
        <div className="cartao__midia">
          <FotoLeilao
            nome={leilao.item.nome}
            categoria={leilao.item.categoria}
            fotos={leilao.item.fotos}
          />
          <SeloEstado estado={leilao.estado} />
        </div>

        <div className="cartao__conteudo">
          <p className="cartao__categoria">{leilao.item.categoria}</p>
          <h3 className="cartao__titulo">{leilao.item.nome}</h3>
          <p className="cartao__tempo">{leilao.tempoEmDestaque(agora)}</p>

          <div className="cartao__rodape">
            <div>
              <span className="cartao__rotulo">{leilao.rotuloPreco}</span>
              <strong className="cartao__preco">
                {formatarBRL(leilao.precoEmDestaque)}
              </strong>
            </div>
            <span className="cartao__seta" aria-hidden="true">
              →
            </span>
          </div>
        </div>
      </Link>
    </article>
  );
}
