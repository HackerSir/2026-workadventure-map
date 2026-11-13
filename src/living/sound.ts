/// <reference types="@workadventure/iframe-api-typings" />

// All audio is synthesised by tools/build_living_world.py.
type Loop = { sound: ReturnType<typeof WA.sound.loadSound>; volume: number };

const cache = new Map<string, ReturnType<typeof WA.sound.loadSound>>();
const loops = new Map<string, Loop>();
let muted = false;

const load = (name: string) => {
  let sound = cache.get(name);
  if (!sound) {
    sound = WA.sound.loadSound(new URL(`audio/${name}.wav`, WA.room.mapURL).toString());
    cache.set(name, sound);
  }
  return sound;
};

const startLoop = ({ sound, volume }: Loop) => sound.play({ volume, loop: true });

export const sfx = (name: string, volume = 0.5) => {
  if (!muted) {
    load(name).play({ volume });
  }
};

export const loop = (name: string, volume: number) => {
  if (loops.has(name)) {
    return;
  }
  const entry = { sound: load(name), volume };
  loops.set(name, entry);
  if (!muted) {
    startLoop(entry);
  }
};

export const stopLoop = (name: string) => {
  loops.get(name)?.sound.stop();
  loops.delete(name);
};

export const isMuted = () => muted;

export const setMuted = (value: boolean) => {
  muted = value;
  for (const entry of loops.values()) {
    if (muted) {
      entry.sound.stop();
    } else {
      startLoop(entry);
    }
  }
  WA.player.state.saveVariable("hsMuted", muted, { public: false, persist: true, scope: "world" });
};

// Every looping track any room plays. Moving between rooms does not reload the game, so the
// previous room's loops would keep playing under the new room's music unless stopped here.
const ALL_LOOPS = ["bgm_town", "wind", "campfire", "bgm_kahoot"];

/** Call before sending the player to another map, including rooms without a script of their own. */
export const stopAllLoops = () => {
  for (const name of ALL_LOOPS) {
    load(name).stop();
  }
  loops.clear();
};

export const initSound = () => {
  muted = WA.player.state.loadVariable("hsMuted") === true;
  stopAllLoops();
};
