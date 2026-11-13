/// <reference types="@workadventure/iframe-api-typings" />

// Player variables do not survive moving between maps for anonymous players, so progress is
// also kept in localStorage. On the live site, map scripts run in a sandbox with no origin and
// cannot use localStorage themselves, so the HUD overlay (served from the map's own site) keeps
// the copy for them: it publishes what it has stored as "hsLocalData" and stores whatever the
// script sends as "hsLocalWrite". When the script can reach localStorage (local development),
// it uses it directly as well.
const LOCAL_PREFIX = "hackersir-town:";
const bus = { public: false, persist: false, scope: "room" } as const;

let fromHud: Record<string, unknown> = {};

const readOwnStorage = (key: string): unknown => {
  try {
    const raw = localStorage.getItem(LOCAL_PREFIX + key);
    return raw === null ? undefined : JSON.parse(raw);
  } catch {
    return undefined;
  }
};

const readLocal = (key: string): unknown => readOwnStorage(key) ?? fromHud[key];

/** Waits (briefly) for the HUD to hand over the stored copy. Call after initUi(). */
export const loadLocalCopy = () =>
  new Promise<void>(resolve => {
    const take = (value: unknown) => {
      if (value && typeof value === "object") {
        fromHud = value as Record<string, unknown>;
        return true;
      }
      return false;
    };
    if (take(WA.player.state.loadVariable("hsLocalData"))) {
      resolve();
      return;
    }
    const subscription = WA.player.state.onVariableChange("hsLocalData").subscribe(value => {
      if (take(value)) {
        clearTimeout(timeout);
        subscription.unsubscribe();
        resolve();
      }
    });
    // Without a HUD (blocked frame, very slow network) the game still works from player variables.
    const timeout = setTimeout(() => {
      subscription.unsubscribe();
      resolve();
    }, 3000);
  });

export const loadSaved = (key: string): unknown => WA.player.state.loadVariable(key) ?? readLocal(key);

/** For lists that only grow, such as cards: whatever either copy has seen counts. */
export const loadSavedList = <T>(key: string): T[] => {
  const lists = [WA.player.state.loadVariable(key), readOwnStorage(key), fromHud[key]].filter(Array.isArray) as T[][];
  return [...new Set(lists.flat())];
};

export const save = async (key: string, value: unknown, isPublic = true) => {
  fromHud = { ...fromHud, [key]: value };
  try {
    localStorage.setItem(LOCAL_PREFIX + key, JSON.stringify(value));
  } catch {
    // Sandboxed script: the HUD stores it instead.
  }
  await WA.player.state.saveVariable("hsLocalWrite", { key, value, at: Date.now() }, bus);
  await WA.player.state.saveVariable(key, value, { public: isPublic, persist: true, scope: "world" });
};
