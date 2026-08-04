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
  // Gesetzt, wenn der Token weder bestätigt noch widerlegt werden konnte.
  const [sessionError, setSessionError] = useState(null);

  const logout = useCallback(() => {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    setToken(null);
    setUser(null);
    setSessionError(null);
  }, []);

  /**
   * Fragt beim Backend nach, wem der Token gehört.
   *
   * Der Ausgang entscheidet über den Token, und zwar nach derselben Regel wie in
   * `apiFetch`: Nur ein `401` heißt "nicht mehr gültig" (docs/auth-api.md). Ein
   * unerreichbares Backend, ein `500` oder eine kaputte Antwort sagen nichts
   * über den Token aus — die Sitzung bleibt bestehen und wird als ungeprüft
   * gemeldet, damit die Oberfläche zum erneuten Versuch einladen kann.
   */
  const verifySession = useCallback(
    (currentToken, signal) => {
      setIsLoading(true);
      setSessionError(null);

      return getCurrentUser(currentToken, { signal })
        .then((currentUser) => {
          setUser(currentUser);
          setIsLoading(false);
        })
        .catch((error) => {
          // Abgebrochen heißt: Die Komponente ist weg oder React hat im
          // StrictMode neu eingehängt. Dann hat dieser Lauf nichts mehr zu
          // melden — vor allem darf er den Token nicht wegwerfen.
          if (signal?.aborted) {
            return;
          }

          if (error instanceof ApiError && error.status === 401) {
            logout();
          } else {
            setSessionError(error);
          }

          setIsLoading(false);
        });
    },
    [logout],
  );

  useEffect(() => {
    // Bewusst nur beim ersten Rendern, daher die leere Abhängigkeitsliste:
    // Geprüft wird der Token, mit dem die Seite geladen wurde. Spätere
    // Änderungen kommen aus `login`/`logout` und bringen den Benutzer schon mit.
    if (!token) {
      setIsLoading(false);
      return undefined;
    }

    const controller = new AbortController();

    verifySession(token, controller.signal);

    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** Der zweite Anlauf, nachdem die Prüfung an der Verbindung gescheitert ist. */
  const retrySession = useCallback(() => {
    if (!token) {
      return;
    }

    verifySession(token);
  }, [token, verifySession]);

  const login = useCallback(async (email, password) => {
    const result = await requestLogin(email, password);

    window.localStorage.setItem(TOKEN_STORAGE_KEY, result.access_token);
    setToken(result.access_token);
    setUser(result.user);
    setSessionError(null);

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
    () => ({
      apiFetch,
      isLoading,
      login,
      logout,
      retrySession,
      sessionError,
      token,
      user,
    }),
    [
      apiFetch,
      isLoading,
      login,
      logout,
      retrySession,
      sessionError,
      token,
      user,
    ],
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
