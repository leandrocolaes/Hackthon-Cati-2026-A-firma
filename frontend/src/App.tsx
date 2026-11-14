import { useEffect } from "react";
import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
import { Cabecalho } from "./components/Cabecalho";
import { Rodape } from "./components/Rodape";
import { Home } from "./pages/Home";
import { LeilaoDetalhe } from "./pages/LeilaoDetalhe";
import { NaoEncontrado } from "./pages/NaoEncontrado";

function RolarAoNavegar() {
  const { pathname } = useLocation();

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "auto" });
  }, [pathname]);

  return null;
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="aplicacao">
        <Cabecalho />
        <RolarAoNavegar />
        <div className="conteudo">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/leiloes/:id" element={<LeilaoDetalhe />} />
            <Route path="*" element={<NaoEncontrado />} />
          </Routes>
        </div>
        <Rodape />
      </div>
    </BrowserRouter>
  );
}
