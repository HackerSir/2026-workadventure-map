/// <reference types="@workadventure/iframe-api-typings" />

// Player variables do not always survive moving between maps (they are not persisted while
// WorkAdventure cannot reach the map's server, and anonymous players have no account to keep
// them in). Map scripts share the game's origin, so localStorage is kept as a backup copy.
const LOCAL_PREFIX = "hackersir-town:";

const readLocal = (key: string): unknown => {
  try {
    const raw = localStorage.getItem(LOCAL_PREFIX + key);
    return raw === null ? undefined : JSON.parse(raw);
  } catch {
    return undefined;
  }
};

export const loadSaved = (key: string): unknown => WA.player.state.loadVariable(key) ?? readLocal(key);

/** For lists that only grow, such as cards: whatever either copy has seen counts. */
export const loadSavedList = <T>(key: string): T[] => {
  const lists = [WA.player.state.loadVariable(key), readLocal(key)].filter(Array.isArray) as T[][];
  return [...new Set(lists.flat())];
};

export const save = async (key: string, value: unknown, isPublic = true) => {
  try {
    localStorage.setItem(LOCAL_PREFIX + key, JSON.stringify(value));
  } catch {
    // Private mode or blocked storage: the player variable is still saved below.
  }
  await WA.player.state.saveVariable(key, value, { public: isPublic, persist: true, scope: "world" });
};
