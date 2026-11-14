// Criação de leilão (RF05, RF06, RF07; HU03). Cada foto vai a POST /api/fotos ao ser
// escolhida; o leilão é criado só com as referências devolvidas pelo servidor.
import { useEffect, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { api, type ErroApi } from "../lib/api";
import { useAuth } from "../lib/auth";
import { formatarBRL } from "../lib/format";

interface ConfigPublica {
  item: { nome_minimo: number; nome_maximo: number; descricao_minima: number; descricao_maxima: number;
          fotos_minimas: number; fotos_maximas: number };
  leilao: { preco_inicial_minimo: string; antecedencia_minima_segundos: number;
            duracao_minima_segundos: number; duracao_maxima_segundos: number };
  foto: { maxima_bytes: number; tipos_permitidos: string[] };
  categorias: string[];
}

interface FotoEnviada {
  referencia: string;
  url: string;
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
  const [fotos, setFotos] = useState<FotoEnviada[]>([]);
  const [enviandoFotos, setEnviandoFotos] = useState(0);
  const [erroFoto, setErroFoto] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    api.get<ConfigPublica>("/api/config-publica").then((c) => { setCfg(c); setCategoria(c.categorias[0]); });
  }, []);

  if (!carregando && !usuario) return <Navigate to="/entrar?voltar=/anunciar" replace />;

  async function escolherFotos(arquivos: FileList | null) {
    if (!cfg || !arquivos) return;
    setErroFoto("");
    const vagas = cfg.item.fotos_maximas - fotos.length - enviandoFotos;
    const lista = Array.from(arquivos).slice(0, Math.max(vagas, 0));
    const avisar = (msg: string) => setErroFoto((atual) => (atual ? `${atual} ${msg}` : msg));
    if (arquivos.length > lista.length) avisar(`No máximo ${cfg.item.fotos_maximas} fotos.`);
    for (const arquivo of lista) {
      // Conferência rápida aqui; quem decide de verdade é o servidor (pelo conteúdo).
      if (arquivo.size > cfg.foto.maxima_bytes) {
        avisar(`"${arquivo.name}" passa de ${Math.floor(cfg.foto.maxima_bytes / 1048576)} MB.`);
        continue;
      }
      setEnviandoFotos((n) => n + 1);
      try {
        const foto = await api.enviarArquivo<FotoEnviada>("/api/fotos", "arquivo", arquivo);
        setFotos((atuais) => [...atuais, foto]);
      } catch (err) {
        avisar(`"${arquivo.name}": ${(err as ErroApi).message}`);
      } finally {
        setEnviandoFotos((n) => n - 1);
      }
    }
  }

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
        fotos: fotos.map((f) => f.referencia), // a ordem aqui é a ordem de exibição
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
          <label className="campo">
            Fotos <small>({fotos.length} de {cfg.item.fotos_minimas}–{cfg.item.fotos_maximas}; a primeira é a capa)</small>
            <input type="file" multiple accept={cfg.foto.tipos_permitidos.join(",")}
              disabled={fotos.length + enviandoFotos >= cfg.item.fotos_maximas}
              onChange={(e) => { escolherFotos(e.target.files); e.target.value = ""; }} />
          </label>
          {(fotos.length > 0 || enviandoFotos > 0) && (
            <div className="miniaturas">
              {fotos.map((f, i) => (
                <div key={f.referencia} className="miniaturas__item">
                  <img src={f.url} alt={`Foto ${i + 1}`} />
                  <button type="button" className="miniaturas__remover" aria-label={`Remover foto ${i + 1}`}
                    onClick={() => setFotos((atuais) => atuais.filter((x) => x.referencia !== f.referencia))}>
                    ×
                  </button>
                </div>
              ))}
              {enviandoFotos > 0 && <p className="detalhe__legenda">Enviando {enviandoFotos} foto(s)…</p>}
            </div>
          )}
          {erroFoto && <p className="aviso-sala" role="alert">{erroFoto}</p>}
          {erro && <p className="aviso-sala" role="alert">{erro}</p>}
          <button className="botao botao--principal botao--largo"
            disabled={enviando || enviandoFotos > 0 || fotos.length < cfg.item.fotos_minimas}>
            {enviando ? "Enviando…" : "Criar leilão"}
          </button>
        </form>
      </article>
    </main>
  );
}
