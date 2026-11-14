interface FotoLeilaoProps {
  nome: string;
  categoria: string;
  fotos: string[];
  grande?: boolean;
}

const iconesPorCategoria: Record<string, string> = {
  Eletrônicos: "◉",
  "Casa e decoração": "⌂",
  Moda: "◇",
  "Esportes e lazer": "⬢",
  Colecionáveis: "✦",
  "Livros e mídia": "▤",
  Outros: "◆",
};

function classeDaCategoria(categoria: string): string {
  return categoria
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z]+/g, "-");
}

export function FotoLeilao({ nome, categoria, fotos, grande = false }: FotoLeilaoProps) {
  const foto = fotos[0];

  if (foto) {
    return (
      <img
        className={`foto-leilao${grande ? " foto-leilao--grande" : ""}`}
        src={foto}
        alt={`Foto de ${nome}`}
        loading="lazy"
      />
    );
  }

  const icone = iconesPorCategoria[categoria] ?? "◆";

  return (
    <div
      className={`foto-leilao foto-leilao--${classeDaCategoria(categoria)}${
        grande ? " foto-leilao--grande" : ""
      }`}
      role="img"
      aria-label={`Imagem ilustrativa de ${nome}`}
    >
      <span className="foto-leilao__icone" aria-hidden="true">
        {icone}
      </span>
      <span className="foto-leilao__legenda">imagem ilustrativa</span>
    </div>
  );
}
