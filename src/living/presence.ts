/// <reference types="@workadventure/iframe-api-typings" />

import { ALL_QUESTS, QUESTS, type Quest } from "./progress";
import { sfx } from "./sound";
import { announce, setOnline } from "./ui";

const FOOTPRINT_LAYER = "floor/hs_trail";
const FOOTPRINT_LIFETIME = 9000;
const TILE = 32;

const footprintTimers = new Map<string, ReturnType<typeof setTimeout>>();
const lastCell = new Map<number, string>();

/** Everyone, including this player, leaves prints in the snow that slowly vanish. */
export const stepInSnow = (playerId: number, x: number, y: number) => {
  const tileX = Math.floor(x / TILE);
  const tileY = Math.floor(y / TILE);
  const cell = `${tileX},${tileY}`;
  if (lastCell.get(playerId) === cell) {
    return;
  }
  lastCell.set(playerId, cell);

  clearTimeout(footprintTimers.get(cell));
  WA.room.setTiles([{ x: tileX, y: tileY, tile: "hs_footprint", layer: FOOTPRINT_LAYER }]);
  footprintTimers.set(
    cell,
    setTimeout(() => {
      footprintTimers.delete(cell);
      WA.room.setTiles([{ x: tileX, y: tileY, tile: null, layer: FOOTPRINT_LAYER }]);
    }, FOOTPRINT_LIFETIME)
  );
};

export const initPresence = async (onSomeoneClearedAll: (name: string) => void) => {
  await WA.players.configureTracking({ players: true, movement: true });

  // Other players are not in list(), so the count includes this player.
  const refreshCount = () => setOnline(Array.from(WA.players.list()).length + 1);
  refreshCount();

  WA.players.onPlayerEnters.subscribe(player => {
    refreshCount();
    announce(`${player.name} 走進了小鎮`);
    sfx("someone", 0.25);
  });

  WA.players.onPlayerLeaves.subscribe(player => {
    refreshCount();
    announce(`${player.name} 離開了小鎮`);
    lastCell.delete(player.playerId);
  });

  WA.players.onPlayerMoves.subscribe(({ player, newPosition }) => {
    stepInSnow(player.playerId, newPosition.x, newPosition.y);
  });

  const known = new Map<number, Quest[]>();
  const arrivedAt = new Map<number, number>();
  for (const player of WA.players.list()) {
    known.set(player.playerId, (player.state.hsCards as Quest[]) ?? []);
  }
  WA.players.onPlayerEnters.subscribe(player => arrivedAt.set(player.playerId, Date.now()));

  WA.players.onVariableChange("hsCards").subscribe(({ player, value }) => {
    const now = (value as Quest[] | undefined) ?? [];
    const before = known.get(player.playerId) ?? [];
    known.set(player.playerId, now);

    // A player's saved cards also arrive as a change just after they join, which is not news.
    const justArrived = Date.now() - (arrivedAt.get(player.playerId) ?? 0) < 5000;
    const gained = now.filter(quest => !before.includes(quest));
    if (!gained.length || justArrived) {
      return;
    }
    if (now.length >= ALL_QUESTS.length) {
      announce(`🎉 ${player.name} 集滿所有卡了！`);
      onSomeoneClearedAll(player.name);
    } else {
      announce(`${player.name} 通過了${QUESTS[gained[0]].name}`);
      sfx("someone", 0.3);
    }
  });

  // Click someone to wave at them.
  WA.ui.onRemotePlayerClicked.subscribe(player => {
    player.addAction("揮手 👋", () => {
      WA.player.state.saveVariable("hsWave", { to: player.playerId, at: Date.now() }, { public: true, persist: false, scope: "room" });
      announce(`你向 ${player.name} 揮了揮手`);
      sfx("wave", 0.4);
    });
  });

  WA.players.onVariableChange("hsWave").subscribe(({ player, value }) => {
    if ((value as { to?: number } | undefined)?.to === WA.player.playerId) {
      announce(`👋 ${player.name} 向你揮手`);
      sfx("wave", 0.5);
    }
  });
};
