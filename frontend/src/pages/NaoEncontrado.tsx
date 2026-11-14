import { Link } from "react-router-dom";

export function NaoEncontrado() {
  return (
    <main className="detalhe">
      <div className="nao-encontrado">
        <p className="etiqueta">Página não encontrada</p>
        <h1>O endereço informado não existe.</h1>
        <p>Volte ao catálogo para consultar os leilões disponíveis.</p>
        <Link className="botao botao--principal" to="/">
          Ver catálogo
        </Link>
      </div>
    </main>
  );
}
