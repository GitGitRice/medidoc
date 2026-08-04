import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  ApiError,
  apiRequest,
  getCurrentUser,
  login as requestLogin,
} from "../api.js";

const TOKEN_STORAGE_KEY = "medidoc.accessToken";
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  // Der Token wird genau einmal aus dem Speicher gelesen — hier. Danach ist
  // dieser State die Wahrheit und `localStorage` nur noch sein Abbild.
  const [token, setToken] = useState(() =>
    window.localStorage.getItem(TOKEN_STORAGE_KEY),
  );
  const [user, setUser] = useState(null);
  // Ohne gespeicherten Token gibt es nichts zu prüfen: sofort fertig.
  const [isLoading, setIsLoading] = useState(Boolean(token));

  const logout = useCallback(() => {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    // Bewusst nur beim ersten Rendern, daher die leere Abhängigkeitsliste:
    // Geprüft wird der Token, mit dem die Seite geladen wurde. Spätere
    // Änderungen kommen aus `login`/`logout` und bringen den Benutzer schon mit.
    if (!token) {
      setIsLoading(false);
      return undefined;
    }

    const controller = new AbortController();

    getCurrentUser(token, { signal: controller.signal })
      .then((currentUser) => {
        setUser(currentUser);
        setIsLoading(false);
      })
      .catch(() => {
        // Abgebrochen heißt: Die Komponente ist weg oder React hat im
        // StrictMode neu eingehängt. Dann hat dieser Lauf nichts mehr zu melden
        // — vor allem darf er den Token nicht wegwerfen.
        if (controller.signal.aborted) {
          return;
        }
        logout();
        setIsLoading(false);
      });

    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = useCallback(async (email, password) => {
    const result = await requestLogin(email, password);

    window.localStorage.setItem(TOKEN_STORAGE_KEY, result.access_token);
    setToken(result.access_token);
    setUser(result.user);

    return result.user;
  }, []);

  /**
   * Der Weg, auf dem geschützte Endpunkte angesprochen werden.
   *
   * Hängt den Token an und setzt die Regel aus docs/auth-api.md um: `401` heißt
   * abgemeldet — Token verwerfen, die Oberfläche landet über `ProtectedRoute`
   * von selbst auf `/login`. Ein `403` bleibt bewusst folgenlos: Da fehlt eine
   * Rolle, nicht die Anmeldung.
   */
  const apiFetch = useCallback(
    async (path, options = {}) => {
      try {
        return await apiRequest(path, { ...options, token });
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          logout();
        }
        throw error;
      }
    },
    [logout, token],
  );

  const value = useMemo(
    () => ({ apiFetch, isLoading, login, logout, token, user }),
    [apiFetch, isLoading, login, logout, token, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth muss innerhalb von AuthProvider verwendet werden.");
  }

  return context;
}
