import { Link, NavLink } from "react-router-dom";
import { useAuth } from "../lib/auth";

export function Cabecalho() {
  const { usuario, sair } = useAuth();
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
          {usuario ? (
            <>
              <NavLink
                to="/anunciar"
                className={({ isActive }) => `navegacao__item${isActive ? " ativo" : ""}`}
              >
                Anunciar
              </NavLink>
              <NavLink
                to="/meus-leiloes"
                className={({ isActive }) => `navegacao__item${isActive ? " ativo" : ""}`}
              >
                Meus leilões
              </NavLink>
              <NavLink
                to="/minhas-participacoes"
                className={({ isActive }) => `navegacao__item${isActive ? " ativo" : ""}`}
              >
                Participações
              </NavLink>
              <span className="navegacao__usuario">Olá, {usuario.nome}</span>
              <button type="button" className="navegacao__item botao-link" onClick={sair}>
                Sair
              </button>
            </>
          ) : (
            <NavLink
              to="/entrar"
              className={({ isActive }) => `navegacao__item${isActive ? " ativo" : ""}`}
            >
              Entrar
            </NavLink>
          )}
        </nav>
      </div>
    </header>
  );
}
