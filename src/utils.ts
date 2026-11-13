/// <reference types="@workadventure/iframe-api-typings" />

export const API_URL = "https://town-tracking.hackersir.org";

export const showToast = (_author: string, message: string, type: "message" | "warning" = "message") => {
  const triggerMessage = WA.ui.displayActionMessage({
    message,
    callback: () => {},
    type,
  });

  setTimeout(() => {
    triggerMessage.remove();
  }, 5000);
};

// Progress lives in the player's own state too (see living/progress.ts), so an unreachable
// server only costs prize redemption and should not interrupt play.
export const loadState = async () => {
  return fetch(`${API_URL}/${WA.player.uuid}/state`)
    .then(res => res.json())
    .catch(e => {
      console.warn("Tracking server unreachable", e);
      return {};
    });
};

export const postState = async (uri: string, payload?: object) => {
  return fetch(`${API_URL}/${WA.player.uuid}/${uri}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: payload && JSON.stringify(payload),
  })
    .then(res => res.json())
    .catch(e => {
      console.warn("Tracking server unreachable", e);
      return undefined;
    });
};

export const wait = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));
