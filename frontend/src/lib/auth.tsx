// Quem está logado, compartilhado por todas as telas (Context API).
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "./api";

export interface Usuario {
  id: number;
  nome: string;
  email: string;
}

interface Auth {
  usuario: Usuario | null;
  carregando: boolean;
  entrar: (email: string, senha: string) => Promise<void>;
  cadastrar: (nome: string, email: string, senha: string) => Promise<void>;
  sair: () => Promise<void>;
  /** Chamado quando uma rota responde 401: a sessão expirou. */
  sessaoExpirou: () => void;
}

const Contexto = createContext<Auth | null>(null);

export function ProvedorAuth({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    // GET /api/eu: 200 com o usuário, ou 401 se não há sessão.
    api.get<Usuario>("/api/eu")
      .then(setUsuario)
      .catch(() => setUsuario(null))
      .finally(() => setCarregando(false));
  }, []);

  const entrar = useCallback(async (email: string, senha: string) => {
    const r = await api.post<{ usuario: Usuario }>("/api/sessao", { email, senha });
    setUsuario(r.usuario);
  }, []);

  const cadastrar = useCallback(async (nome: string, email: string, senha: string) => {
    // O cadastro não abre sessão (contrato): cadastra e, em seguida, entra.
    await api.post("/api/usuarios", { nome, email, senha });
    await entrar(email, senha);
  }, [entrar]);

  const sair = useCallback(async () => {
    await api.delete("/api/sessao").catch(() => {});
    setUsuario(null);
  }, []);

  const sessaoExpirou = useCallback(() => setUsuario(null), []);

  return (
    <Contexto.Provider value={{ usuario, carregando, entrar, cadastrar, sair, sessaoExpirou }}>
      {children}
    </Contexto.Provider>
  );
}

export function useAuth(): Auth {
  const ctx = useContext(Contexto);
  if (!ctx) throw new Error("useAuth fora do ProvedorAuth");
  return ctx;
}
