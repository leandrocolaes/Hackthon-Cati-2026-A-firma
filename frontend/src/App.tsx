import { useEffect } from "react";
import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
import { Cabecalho } from "./components/Cabecalho";
import { ProvedorAuth } from "./lib/auth";
import { Anunciar } from "./pages/Anunciar";
import { Entrar } from "./pages/Entrar";
import { Rodape } from "./components/Rodape";
import { Home } from "./pages/Home";
import { LeilaoDetalhe } from "./pages/LeilaoDetalhe";
import { MeusLeiloes } from "./pages/MeusLeiloes";
import { NaoEncontrado } from "./pages/NaoEncontrado";
import { PerfilComitente } from "./pages/PerfilComitente";

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
      <ProvedorAuth>
      <div className="aplicacao">
        <Cabecalho />
        <RolarAoNavegar />
        <div className="conteudo">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/leiloes" element={<Home />} />
            <Route path="/leiloes/:id" element={<LeilaoDetalhe />} />
            <Route path="/entrar" element={<Entrar />} />
            <Route path="/anunciar" element={<Anunciar />} />
            <Route path="/leiloes/:id/editar" element={<Anunciar />} />
            <Route path="/meus-leiloes" element={<MeusLeiloes />} />
            <Route path="/comitentes/:ref" element={<PerfilComitente />} />
            <Route path="*" element={<NaoEncontrado />} />
          </Routes>
        </div>
        <Rodape />
      </div>
      </ProvedorAuth>
    </BrowserRouter>
  );
}
