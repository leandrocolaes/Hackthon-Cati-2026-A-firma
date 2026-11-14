// Login e cadastro na mesma tela (RF01, RF02; HU01, HU02).
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../lib/auth";

export function Entrar() {
  const { entrar, cadastrar } = useAuth();
  const [params] = useSearchParams();
  const navegar = useNavigate();
  const [modo, setModo] = useState<"login" | "cadastro">("login");
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setErro("");
    setEnviando(true);
    try {
      if (modo === "login") await entrar(email, senha);
      else await cadastrar(nome, email, senha);
      navegar(params.get("voltar") || "/", { replace: true });
    } catch (err) {
      setErro((err as Error).message);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <main className="detalhe">
      <Link className="voltar" to="/">← Voltar para o catálogo</Link>
      <article className="detalhe__painel formulario">
        <p className="etiqueta">{modo === "login" ? "Acesso" : "Nova conta"}</p>
        <h1>{modo === "login" ? "Entrar" : "Criar conta"}</h1>
        <form onSubmit={enviar}>
          {modo === "cadastro" && (
            <label className="campo">
              Nome de exibição
              <input value={nome} onChange={(e) => setNome(e.target.value)} required maxLength={100} />
            </label>
          )}
          <label className="campo">
            E-mail
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label className="campo">
            Senha {modo === "cadastro" && <small>(mínimo 8 caracteres)</small>}
            <input type="password" value={senha} onChange={(e) => setSenha(e.target.value)} required
              minLength={modo === "cadastro" ? 8 : 1} />
          </label>
          {erro && <p className="aviso-sala" role="alert">{erro}</p>}
          <button className="botao botao--principal botao--largo" disabled={enviando}>
            {enviando ? "Aguarde…" : modo === "login" ? "Entrar" : "Criar conta e entrar"}
          </button>
        </form>
        <button type="button" className="botao-link"
          onClick={() => { setModo(modo === "login" ? "cadastro" : "login"); setErro(""); }}>
          {modo === "login" ? "Não tem conta? Cadastre-se" : "Já tem conta? Entrar"}
        </button>
      </article>
    </main>
  );
}
