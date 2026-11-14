interface PaginacaoProps {
  pagina: number;
  totalPaginas: number;
  aoMudar: (pagina: number) => void;
}

export function Paginacao({ pagina, totalPaginas, aoMudar }: PaginacaoProps) {
  if (totalPaginas <= 1) {
    return null;
  }

  return (
    <nav className="paginacao" aria-label="Paginação do catálogo">
      <button
        type="button"
        className="paginacao__botao"
        onClick={() => aoMudar(pagina - 1)}
        disabled={pagina === 1}
      >
        ← Anterior
      </button>
      <span className="paginacao__posicao">
        Página {pagina} de {totalPaginas}
      </span>
      <button
        type="button"
        className="paginacao__botao"
        onClick={() => aoMudar(pagina + 1)}
        disabled={pagina === totalPaginas}
      >
        Próxima →
      </button>
    </nav>
  );
}
