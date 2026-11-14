// Criação de leilão (RF05, RF06; HU03). Fotos chegam com o F11 (POST /api/fotos).
import { useEffect, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { formatarBRL } from "../lib/format";

interface ConfigPublica {
  item: { nome_minimo: number; nome_maximo: number; descricao_minima: number; descricao_maxima: number;
          fotos_minimas: number; fotos_maximas: number };
  leilao: { preco_inicial_minimo: string; antecedencia_minima_segundos: number;
            duracao_minima_segundos: number; duracao_maxima_segundos: number };
  categorias: string[];
}

// <input type="datetime-local"> usa "AAAA-MM-DDTHH:MM" no horário LOCAL de quem preenche.
function paraCampoLocal(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

export function Anunciar() {
  const { usuario, carregando } = useAuth();
  const navegar = useNavigate();
  const [cfg, setCfg] = useState<ConfigPublica | null>(null);
  const [nome, setNome] = useState("");
  const [descricao, setDescricao] = useState("");
  const [categoria, setCategoria] = useState("");
  const [preco, setPreco] = useState("");
  const [inicio, setInicio] = useState(() => paraCampoLocal(new Date(Date.now() + 2 * 60_000)));
  const [duracaoMin, setDuracaoMin] = useState("3");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    api.get<ConfigPublica>("/api/config-publica").then((c) => { setCfg(c); setCategoria(c.categorias[0]); });
  }, []);

  if (!carregando && !usuario) return <Navigate to="/entrar?voltar=/anunciar" replace />;

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setErro("");
    setEnviando(true);
    try {
      const r = await api.post<{ id: number }>("/api/leiloes", {
        nome, descricao, categoria,
        preco_inicial: preco.trim().replace(",", "."),
        // Horário digitado é LOCAL; toISOString() envia o instante em UTC com "Z" (RF19).
        inicio: new Date(inicio).toISOString(),
        duracao_segundos: Math.round(Number(duracaoMin) * 60),
        fotos: [], // F11
      });
      navegar(`/leiloes/${r.id}`);
    } catch (err) {
      setErro((err as Error).message);
    } finally {
      setEnviando(false);
    }
  }

  if (!cfg) return <main className="detalhe"><p className="detalhe__legenda">Carregando…</p></main>;
  return (
    <main className="detalhe">
      <Link className="voltar" to="/">← Voltar para o catálogo</Link>
      <article className="detalhe__painel formulario">
        <p className="etiqueta">Novo anúncio</p>
        <h1>Anunciar item</h1>
        <form onSubmit={enviar}>
          <label className="campo">
            Nome <small>({cfg.item.nome_minimo}–{cfg.item.nome_maximo} caracteres)</small>
            <input value={nome} onChange={(e) => setNome(e.target.value)} required
              minLength={cfg.item.nome_minimo} maxLength={cfg.item.nome_maximo} />
          </label>
          <label className="campo">
            Descrição <small>({cfg.item.descricao_minima}–{cfg.item.descricao_maxima} caracteres)</small>
            <textarea rows={4} value={descricao} onChange={(e) => setDescricao(e.target.value)} required
              minLength={cfg.item.descricao_minima} maxLength={cfg.item.descricao_maxima} />
          </label>
          <label className="campo">
            Categoria
            <select value={categoria} onChange={(e) => setCategoria(e.target.value)}>
              {cfg.categorias.map((c) => <option key={c}>{c}</option>)}
            </select>
          </label>
          <label className="campo">
            Preço inicial <small>(mínimo {formatarBRL(cfg.leilao.preco_inicial_minimo)})</small>
            <input inputMode="decimal" placeholder="150.00" value={preco} onChange={(e) => setPreco(e.target.value)} required />
          </label>
          <label className="campo">
            Início <small>(seu horário local)</small>
            <input type="datetime-local" value={inicio} onChange={(e) => setInicio(e.target.value)} required />
          </label>
          <label className="campo">
            Duração em minutos
            <input type="number" step="any" value={duracaoMin} onChange={(e) => setDuracaoMin(e.target.value)} required
              min={cfg.leilao.duracao_minima_segundos / 60} max={cfg.leilao.duracao_maxima_segundos / 60} />
          </label>
          {cfg.item.fotos_minimas > 0 && (
            <p className="aviso-sala">
              O envio de fotos ainda não está disponível e o servidor exige {cfg.item.fotos_minimas} foto(s).
              Até lá, a criação será recusada (em desenvolvimento, use ITEM_MIN_PHOTOS=0).
            </p>
          )}
          {erro && <p className="aviso-sala" role="alert">{erro}</p>}
          <button className="botao botao--principal botao--largo" disabled={enviando}>
            {enviando ? "Enviando…" : "Criar leilão"}
          </button>
        </form>
      </article>
    </main>
  );
}
