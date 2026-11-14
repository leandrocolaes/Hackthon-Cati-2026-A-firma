import { Link, NavLink } from "react-router-dom";

export function Cabecalho() {
  return (
    <header className="cabecalho">
      <div className="cabecalho__conteudo">
        <Link className="marca" to="/" aria-label="A Firma Leilões — página inicial">
          <span className="marca__monograma" aria-hidden="true">
            AF
          </span>
          <span className="marca__texto">
            <strong>A Firma</strong>
            <small>Leilões</small>
          </span>
        </Link>

        <nav className="navegacao" aria-label="Navegação principal">
          <NavLink
            to="/"
            className={({ isActive }) => `navegacao__item${isActive ? " ativo" : ""}`}
          >
            Leilões
          </NavLink>
          <span className="navegacao__ambiente">ambiente de demonstração</span>
        </nav>
      </div>
    </header>
  );
}
