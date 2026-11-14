import { createRoot } from "react-dom/client";
import App from "./App";
import "./estilos.css";

// Pega a <div id="root"> do index.html e desenha o React dentro dela.
createRoot(document.getElementById("root")!).render(<App />);
