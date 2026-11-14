import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Leilao } from "../classes/Leilao";
import { CartaoLeilao } from "../components/CartaoLeilao";
import { Paginacao } from "../components/Paginacao";
import { api, leilaoDoCartao, type CartaoApi } from "../lib/api";
import { useRelogio } from "../lib/useRelogio";

const POR_PAGINA = 20;
// RF21: a lista se atualiza sozinha a cada 15 s (estado e preço mudam).
const ATUALIZAR_MS = 15_000;
const BUSCA_ADIADA_MS = 350;

interface PaginaCatalogo {
  itens: CartaoApi[];
  pagina: number;
  por_pagina: number;
  total: number;
}

type Ordem = "padrao" | "termina" | "comeca" | "preco_asc" | "preco_desc";
type EstadoFiltro = "todos" | "em_andamento" | "agendado";

const ORDENS: { valor: Ordem; rotulo: string }[] = [
  { valor: "padrao", rotulo: "Padrão (em andamento primeiro)" },
  { valor: "termina", rotulo: "Termina primeiro" },
  { valor: "comeca", rotulo: "Começa primeiro" },
  { valor: "preco_asc", rotulo: "Menor preço" },
  { valor: "preco_desc", rotulo: "Maior preço" },
];

function ehOrdem(valor: string | null): valor is Ordem {
  return ORDENS.some((ordem) => ordem.valor === valor);
}

function ehEstado(valor: string | null): valor is Exclude<EstadoFiltro, "todos"> {
  return valor === "em_andamento" || valor === "agendado";
}

function paginaDaUrl(valor: string | null): number {
  const numero = Number(valor);
  return Number.isInteger(numero) && numero > 0 ? numero : 1;
}

/** RF21: aceita "1.234,50" (vírgula decimal) e "1234.50"; a API valida o resto (422). */
function precoParaApi(texto: string): string {
  const limpo = texto.trim();
  return limpo.includes(",") ? limpo.replace(/\./g, "").replace(",", ".") : limpo;
}

/** Espera o usuário parar de digitar antes de consultar a API. */
function useValorAdiado<T>(valor: T, atraso: number): T {
  const [adiado, setAdiado] = useState(valor);
  useEffect(() => {
    const timer = window.setTimeout(() => setAdiado(valor), atraso);
    return () => window.clearTimeout(timer);
  }, [valor, atraso]);
  return adiado;
}

export function Home() {
  const agora = useRelogio();
  const [parametros, setParametros] = useSearchParams();

  const busca = parametros.get("busca") ?? "";
  const categoria = parametros.get("categoria") ?? "todas";
  const estadoParam = parametros.get("estado");
  const estado: EstadoFiltro = ehEstado(estadoParam) ? estadoParam : "todos";
  const precoMin = parametros.get("preco_min") ?? "";
  const precoMax = parametros.get("preco_max") ?? "";
  const ordenarParam = parametros.get("ordenar");
  const ordenar: Ordem = ehOrdem(ordenarParam) ? ordenarParam : "padrao";
  const pagina = paginaDaUrl(parametros.get("pagina"));
  const buscaAdiada = useValorAdiado(busca, BUSCA_ADIADA_MS);

  const [categorias, setCategorias] = useState<string[]>([]);
  const [itens, setItens] = useState<Leilao[]>([]);
  const [total, setTotal] = useState(0);
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(true);

  // As categorias do filtro são as configuradas no servidor, não só as da página atual.
  useEffect(() => {
    api.get<{ categorias: string[] }>("/api/config-publica")
      .then((c) => setCategorias(c.categorias))
      .catch(() => { /* o catálogo ainda funciona; só não preenche as opções */ });
  }, []);

  const consulta = useMemo(() => {
    const p = new URLSearchParams();
    p.set("pagina", String(pagina));
    p.set("por_pagina", String(POR_PAGINA));
    if (buscaAdiada.trim()) p.set("busca", buscaAdiada.trim());
    if (categoria !== "todas") p.set("categoria", categoria);
    if (estado !== "todos") p.set("estado", estado);
    if (precoMin.trim()) p.set("preco_min", precoParaApi(precoMin));
    if (precoMax.trim()) p.set("preco_max", precoParaApi(precoMax));
    if (ordenar !== "padrao") p.set("ordenar", ordenar);
    return p.toString();
  }, [pagina, buscaAdiada, categoria, estado, precoMin, precoMax, ordenar]);

  useEffect(() => {
    let ativo = true;
    const carregar = () =>
      api.get<PaginaCatalogo>(`/api/leiloes?${consulta}`)
        .then((r) => {
          if (!ativo) return;
          setItens(r.itens.map(leilaoDoCartao));
          setTotal(r.total);
          setErro("");
          setCarregando(false);
        })
        .catch((e) => {
          if (!ativo) return;
          setErro(e.message);
          setCarregando(false);
        });
    carregar();
    const timer = window.setInterval(carregar, ATUALIZAR_MS);
    return () => { ativo = false; window.clearInterval(timer); };
  }, [consulta]);

  const totalPaginas = Math.max(1, Math.ceil(total / POR_PAGINA));
  const inicio = (pagina - 1) * POR_PAGINA;
  const temFiltro =
    busca.trim() !== "" ||
    categoria !== "todas" ||
    estado !== "todos" ||
    precoMin.trim() !== "" ||
    precoMax.trim() !== "" ||
    ordenar !== "padrao";

  // Uma URL antiga pode apontar para uma página que não existe mais após filtrar.
  useEffect(() => {
    if (carregando || pagina <= totalPaginas) return;
    const proximos = new URLSearchParams(parametros);
    if (totalPaginas > 1) proximos.set("pagina", String(totalPaginas));
    else proximos.delete("pagina");
    setParametros(proximos, { replace: true });
  }, [carregando, pagina, totalPaginas, parametros, setParametros]);

  function atualizar(mudancas: Record<string, string>, novaPagina = 1) {
    const proximos = new URLSearchParams(parametros);
    for (const [chave, valor] of Object.entries(mudancas)) {
      const limpo = valor.trim();
      const padrao =
        (chave === "categoria" && limpo === "todas") ||
        (chave === "estado" && limpo === "todos") ||
        (chave === "ordenar" && limpo === "padrao");
      if (!limpo || padrao) proximos.delete(chave);
      else proximos.set(chave, limpo);
    }
    if (novaPagina > 1) proximos.set("pagina", String(novaPagina));
    else proximos.delete("pagina");
    setParametros(proximos, { replace: true });
  }

  function mudarPagina(novaPagina: number) {
    const limite = Math.min(Math.max(novaPagina, 1), totalPaginas);
    const proximos = new URLSearchParams(parametros);
    if (limite > 1) proximos.set("pagina", String(limite));
    else proximos.delete("pagina");
    setParametros(proximos, { replace: true });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function limparFiltros() {
    setParametros(new URLSearchParams(), { replace: true });
  }

  return (
    <main>
      <section className="hero" aria-labelledby="titulo-principal">
        <div className="hero__texto">
          <p className="etiqueta etiqueta--clara">Leilão online ao vivo</p>
          <h1 id="titulo-principal">
            Objetos com história,
            <br />
            <em>disputas em tempo real.</em>
          </h1>
          <p className="hero__descricao">
            Descubra peças únicas, acompanhe cada lance e encontre o próximo
            item da sua coleção. O catálogo é público; a sala de disputa é para
            quem está autenticado.
          </p>
          <div className="hero__acoes">
            <a className="botao botao--dourado" href="#catalogo">
              Explorar leilões
            </a>
            <span className="hero__nota">
              {carregando ? "Carregando catálogo…" : `${total} anúncio${total === 1 ? "" : "s"} encontrado${total === 1 ? "" : "s"}`}
            </span>
          </div>
        </div>

        <aside className="hero__painel" aria-label="Resumo do catálogo">
          <div className="hero__numero">
            <strong>{total}</strong>
            <span>resultados</span>
          </div>
          <div className="hero__numero">
            <strong>{itens.length}</strong>
            <span>nesta página</span>
          </div>
          <div className="hero__numero">
            <strong>{categorias.length}</strong>
            <span>categorias</span>
          </div>
          <p className="hero__painel-nota">
            Em andamento aparecem primeiro. Use os filtros para refinar a busca.
          </p>
        </aside>
      </section>

      <section className="catalogo" id="catalogo" aria-labelledby="titulo-catalogo">
        <div className="secao__cabecalho">
          <div>
            <p className="etiqueta">Catálogo público</p>
            <h2 id="titulo-catalogo">Leilões abertos</h2>
          </div>
          <p className="secao__descricao">
            {carregando && itens.length === 0
              ? "Carregando leilões…"
              : total === 0
                ? temFiltro
                  ? "Nenhum leilão corresponde aos filtros."
                  : "Nenhum leilão disponível no momento."
                : `Mostrando ${inicio + 1}–${Math.min(inicio + POR_PAGINA, total)} de ${total} ${
                    total === 1 ? "resultado" : "resultados"
                  }.`}
          </p>
        </div>

        <div className="busca" role="search" aria-label="Buscar e filtrar leilões">
          <label className="busca__campo busca__campo--texto">
            <span className="busca__rotulo">Buscar</span>
            <input
              type="search"
              value={busca}
              onChange={(e) => atualizar({ busca: e.target.value })}
              placeholder="Parte do nome do item..."
              autoComplete="off"
            />
          </label>

          <label className="busca__campo busca__campo--categoria">
            <span className="busca__rotulo">Categoria</span>
            <select
              value={categoria}
              onChange={(e) => atualizar({ categoria: e.target.value })}
            >
              <option value="todas">Todas as categorias</option>
              {categorias.map((c) => <option key={c} value={c}>{c}</option>)}
              {categoria !== "todas" && !categorias.includes(categoria) && (
                <option value={categoria}>{categoria}</option>
              )}
            </select>
          </label>

          <label className="busca__campo busca__campo--estado">
            <span className="busca__rotulo">Estado</span>
            <select
              value={estado}
              onChange={(e) => atualizar({ estado: e.target.value })}
            >
              <option value="todos">Todos os estados</option>
              <option value="em_andamento">Em andamento</option>
              <option value="agendado">Agendados</option>
            </select>
          </label>

          <label className="busca__campo busca__campo--preco">
            <span className="busca__rotulo">Preço mínimo</span>
            <input
              type="number"
              min="0"
              step="0.01"
              inputMode="decimal"
              value={precoMin}
              onChange={(e) => atualizar({ preco_min: e.target.value })}
              placeholder="R$ 0,00"
            />
          </label>

          <label className="busca__campo busca__campo--preco">
            <span className="busca__rotulo">Preço máximo</span>
            <input
              type="number"
              min="0"
              step="0.01"
              inputMode="decimal"
              value={precoMax}
              onChange={(e) => atualizar({ preco_max: e.target.value })}
              placeholder="Sem limite"
            />
          </label>

          <label className="busca__campo busca__campo--ordem">
            <span className="busca__rotulo">Ordenar por</span>
            <select
              value={ordenar}
              onChange={(e) => atualizar({ ordenar: e.target.value })}
            >
              {ORDENS.map((o) => <option key={o.valor} value={o.valor}>{o.rotulo}</option>)}
            </select>
          </label>

          <button
            type="button"
            className="botao botao--contorno busca__limpar"
            onClick={limparFiltros}
            disabled={!temFiltro}
          >
            Limpar filtros
          </button>
        </div>

        {erro && (
          <p className="aviso-demonstracao" role="alert">
            <span aria-hidden="true">●</span>
            Não foi possível carregar os leilões: {erro}
          </p>
        )}

        {itens.length === 0 ? (
          <div className="estado-vazio">
            {carregando ? (
              <p>Carregando leilões…</p>
            ) : temFiltro ? (
              <>
                <p>Nenhum leilão encontrado com os filtros selecionados.</p>
                <button type="button" className="botao-link" onClick={limparFiltros}>
                  Limpar busca e filtros
                </button>
              </>
            ) : (
              <p>Não há leilões agendados ou em andamento para exibir.</p>
            )}
          </div>
        ) : (
          <div className="grade">
            {itens.map((leilao) => (
              <CartaoLeilao key={leilao.id} leilao={leilao} agora={agora} />
            ))}
          </div>
        )}

        <Paginacao
          pagina={pagina}
          totalPaginas={totalPaginas}
          aoMudar={mudarPagina}
        />
      </section>
    </main>
  );
}
