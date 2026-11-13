/// <reference types="@workadventure/iframe-api-typings" />

import type { UIWebsite } from "@workadventure/iframe-api-typings";
import { ALL_QUESTS, getCards, onProgress } from "./progress";
import { isMuted, setMuted } from "./sound";

// overlay/*.html run in their own iframes, so scripts and overlays talk through player variables.
const bus = (key: string, value: unknown) =>
  WA.player.state.saveVariable(key, value, { public: false, persist: false, scope: "room" });

const overlayUrl = (name: string) => new URL(`overlay/${name}.html`, WA.room.mapURL).toString();

export type Speaker = { name: string; portrait?: string };
export type Option = { id: string; label: string };

let dialogSite: UIWebsite | undefined;
let pending: ((choice: string | null) => void) | undefined;
let sequence = 0;
let online = 0;
let objective = "";
let feed: { id: number; text: string }[] = [];
let feedId = 0;

const pushHud = () => bus("hsHud", { cards: getCards(), total: ALL_QUESTS.length, online, feed, muted: isMuted(), objective });

/** A line under the HUD, such as a countdown. An empty string hides it. */
export const setObjective = (text: string) => {
  objective = text;
  pushHud();
};

/** Opens a full overlay page, such as the phishing mail, and returns a function that closes it. */
export const openPage = async (name: string) => {
  const site = await WA.ui.website.open({
    url: overlayUrl(name),
    allowApi: true,
    visible: true,
    position: { vertical: "middle", horizontal: "middle" },
    size: { width: "min(760px, 96vw)", height: "min(620px, 86vh)" },
  });
  return () => site.close();
};

export const setOnline = (count: number) => {
  online = count;
  pushHud();
};

export const announce = (text: string) => {
  feed = [...feed.slice(-2), { id: ++feedId, text }];
  pushHud();
  const id = feedId;
  setTimeout(() => {
    feed = feed.filter(item => item.id !== id);
    pushHud();
  }, 9000);
};

export const closeDialog = () => {
  pending?.(null);
  pending = undefined;
  bus("hsDialog", null);
  if (dialogSite) {
    dialogSite.visible = false;
  }
};

/** Shows a line. With options, resolves to the chosen id, or null if the player walked away. */
export const say = (speaker: Speaker, text: string, options: Option[] = []) => {
  pending?.(null);
  pending = undefined;
  const seq = ++sequence;
  const portrait = speaker.portrait ? new URL(`portraits/${speaker.portrait}.png`, WA.room.mapURL).toString() : undefined;
  bus("hsDialog", { seq, name: speaker.name, portrait, text, options });
  if (dialogSite) {
    dialogSite.visible = true;
  }
  return new Promise<string | null>(resolve => {
    if (options.length) {
      pending = resolve;
    } else {
      resolve(null);
    }
  });
};

export const initUi = async () => {
  await WA.ui.website.open({
    url: overlayUrl("hud"),
    allowApi: true,
    visible: true,
    position: { vertical: "top", horizontal: "left" },
    size: { width: "330px", height: "190px" },
    margin: { top: "8px", left: "8px" },
  });

  dialogSite = await WA.ui.website.open({
    url: overlayUrl("dialog"),
    allowApi: true,
    visible: false,
    position: { vertical: "bottom", horizontal: "middle" },
    size: { width: "min(680px, 96vw)", height: "210px" },
    margin: { bottom: "84px" },
  });

  WA.player.state.onVariableChange("hsPick").subscribe(value => {
    const pick = value as { seq: number; id: string } | null;
    if (pick && pick.seq === sequence && pending) {
      const resolve = pending;
      pending = undefined;
      resolve(pick.id);
    }
  });

  WA.player.state.onVariableChange("hsHudCommand").subscribe(value => {
    if ((value as { action?: string } | null)?.action === "toggleMute") {
      setMuted(!isMuted());
      pushHud();
    }
  });

  onProgress(pushHud);
  pushHud();
};
