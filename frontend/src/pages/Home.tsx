import { useEffect, useMemo, useState } from "react";
import { Leilao } from "../classes/Leilao";
import { CartaoLeilao } from "../components/CartaoLeilao";
import { Paginacao } from "../components/Paginacao";
import { api, leilaoDoCartao, type CartaoApi } from "../lib/api";
import { useRelogio } from "../lib/useRelogio";

const POR_PAGINA = 20;
// Busca até 100 leilões (máximo da API) e pagina na tela, como antes.
// DECISAO: a lista se atualiza sozinha a cada 15 s (estado e preço mudam).
const ATUALIZAR_MS = 15_000;

/** Busca sem diferenciar maiúsculas nem acentos ("eletronicos" encontra "Eletrônicos"). */
function normalizarBusca(texto: string): string {
  return texto
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

export function Home() {
  const agora = useRelogio();
  const [pagina, setPagina] = useState(1);
  const [busca, setBusca] = useState("");
  const [categoriaFiltro, setCategoriaFiltro] = useState("todas");
  const [estadoFiltro, setEstadoFiltro] = useState("todos");

  const [leiloes, setLeiloes] = useState<Leilao[]>([]);
  const [erro, setErro] = useState("");

  useEffect(() => {
    let ativo = true;
    const carregar = () =>
      api.get<{ itens: CartaoApi[] }>("/api/leiloes?pagina=1&por_pagina=100")
        .then((r) => { if (ativo) { setLeiloes(r.itens.map(leilaoDoCartao)); setErro(""); } })
        .catch((e) => ativo && setErro(e.message));
    carregar();
    const timer = window.setInterval(carregar, ATUALIZAR_MS);
    return () => { ativo = false; window.clearInterval(timer); };
  }, []);

  const catalogo = useMemo(() => Leilao.catalogo(leiloes), [leiloes]);
  const emAndamento = catalogo.filter((leilao) => leilao.emAndamento).length;
  const agendados = catalogo.filter((leilao) => leilao.agendado).length;
  const categorias = new Set(catalogo.map((leilao) => leilao.item.categoria)).size;

  const categoriasDisponiveis = useMemo(
    () => [...new Set(catalogo.map((leilao) => leilao.item.categoria))].sort((a, b) => a.localeCompare(b, "pt-BR")),
    [catalogo],
  );

  const filtrados = useMemo(() => {
    const termo = normalizarBusca(busca);
    return catalogo.filter((leilao) => {
      const combinaBusca =
        termo === "" ||
        normalizarBusca(leilao.item.nome).includes(termo) ||
        normalizarBusca(leilao.item.categoria).includes(termo);
      const combinaCategoria =
        categoriaFiltro === "todas" || leilao.item.categoria === categoriaFiltro;
      const combinaEstado =
        estadoFiltro === "todos" ||
        (estadoFiltro === "em_andamento" ? leilao.emAndamento : leilao.agendado);
      return combinaBusca && combinaCategoria && combinaEstado;
    });
  }, [catalogo, busca, categoriaFiltro, estadoFiltro]);

  const temFiltro =
    busca.trim() !== "" || categoriaFiltro !== "todas" || estadoFiltro !== "todos";

  // Qualquer mudança de filtro volta para a primeira página.
  useEffect(() => {
    setPagina(1);
  }, [busca, categoriaFiltro, estadoFiltro]);

  const totalPaginas = Math.max(1, Math.ceil(filtrados.length / POR_PAGINA));
  const inicio = (pagina - 1) * POR_PAGINA;
  const visiveis = filtrados.slice(inicio, inicio + POR_PAGINA);

  // A atualização automática pode reduzir a lista enquanto estamos numa página alta.
  useEffect(() => {
    setPagina((atual) => Math.min(atual, totalPaginas));
  }, [totalPaginas]);

  function mudarPagina(novaPagina: number) {
    setPagina(Math.min(Math.max(novaPagina, 1), totalPaginas));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function limparFiltros() {
    setBusca("");
    setCategoriaFiltro("todas");
    setEstadoFiltro("todos");
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
              {catalogo.length} anúncios no catálogo
            </span>
          </div>
        </div>

        <aside className="hero__painel" aria-label="Resumo do catálogo">
          <div className="hero__numero">
            <strong>{emAndamento}</strong>
            <span>em andamento</span>
          </div>
          <div className="hero__numero">
            <strong>{agendados}</strong>
            <span>agendados</span>
          </div>
          <div className="hero__numero">
            <strong>{categorias}</strong>
            <span>categorias</span>
          </div>
          <p className="hero__painel-nota">
            Em andamento aparecem primeiro, pelo término mais próximo.
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
            {catalogo.length === 0
              ? "Nenhum leilão disponível no momento."
              : filtrados.length === 0
                ? "Nenhum leilão corresponde aos filtros."
                : `Mostrando ${inicio + 1}–${Math.min(
                    inicio + POR_PAGINA,
                    filtrados.length,
                  )} de ${filtrados.length} ${
                    temFiltro
                      ? `resultado${filtrados.length === 1 ? "" : "s"}`
                      : "leilões elegíveis"
                  }${temFiltro ? ` (de ${catalogo.length})` : ""}.`}
          </p>
        </div>

        <div className="busca" role="search" aria-label="Buscar e filtrar leilões">
          <label className="busca__campo busca__campo--texto">
            <span className="busca__rotulo">Buscar</span>
            <input
              type="search"
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder="Nome do item ou categoria..."
              autoComplete="off"
            />
          </label>

          <label className="busca__campo">
            <span className="busca__rotulo">Categoria</span>
            <select
              value={categoriaFiltro}
              onChange={(e) => setCategoriaFiltro(e.target.value)}
            >
              <option value="todas">Todas as categorias</option>
              {categoriasDisponiveis.map((categoria) => (
                <option key={categoria} value={categoria}>{categoria}</option>
              ))}
            </select>
          </label>

          <label className="busca__campo">
            <span className="busca__rotulo">Estado</span>
            <select
              value={estadoFiltro}
              onChange={(e) => setEstadoFiltro(e.target.value)}
            >
              <option value="todos">Todos os estados</option>
              <option value="em_andamento">Em andamento</option>
              <option value="agendado">Agendados</option>
            </select>
          </label>

          <button
            type="button"
            className="busca__limpar"
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

        {visiveis.length === 0 ? (
          <div className="estado-vazio">
            {temFiltro ? (
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
            {visiveis.map((leilao) => (
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
