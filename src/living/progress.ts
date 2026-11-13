/// <reference types="@workadventure/iframe-api-typings" />

import { loadState } from "../utils";
import { loadSavedList, save } from "./saved";

export type Quest = "cardgame" | "sheepwall" | "cryptogame" | "kahoot" | "office";

export const QUESTS: Record<Quest, { name: string; reward: string }> = {
  cardgame: { name: "翻牌遊戲", reward: "神聖彗星反射力量陷阱卡" },
  sheepwall: { name: "腳捲綿羊牆", reward: "腳捲綿羊遊戲卡" },
  cryptogame: { name: "解密客棧", reward: "單字卡" },
  kahoot: { name: "解謎屋", reward: "好人卡" },
  office: { name: "辦公室找碴", reward: "辦公室通行卡" },
};

export const ALL_QUESTS = Object.keys(QUESTS) as Quest[];

const listeners: Array<(cards: Quest[], gained?: Quest) => void> = [];
let cards: Quest[] = [];

// Public, so that other players can see and celebrate this player's progress.
const saveCards = () => save("hsCards", cards);

const emit = (gained?: Quest) => listeners.forEach(listener => listener(cards, gained));

export const getCards = () => cards;
export const missingQuests = () => ALL_QUESTS.filter(quest => !cards.includes(quest));
export const hasAllCards = () => cards.length === ALL_QUESTS.length;
export const onProgress = (listener: (cards: Quest[], gained?: Quest) => void) => listeners.push(listener);

export const townClears = () => Number(WA.state.loadVariable("townClears")) || 0;

/**
 * Adds this player's not-yet-counted cards to the town-wide total that lights the plaza tree.
 * Only the main map declares that variable, so cards won in other rooms are counted on return.
 */
export const countTownClears = async () => {
  const counted = loadSavedList<Quest>("hsCounted");
  const fresh = cards.filter(quest => !counted.includes(quest));
  if (!fresh.length) {
    return;
  }
  await save("hsCounted", [...counted, ...fresh], false);
  await WA.state.saveVariable("townClears", townClears() + fresh.length);
};

export const addCard = async (quest: Quest) => {
  if (cards.includes(quest)) {
    return false;
  }
  cards = [...cards, quest];
  await saveCards();
  emit(quest);
  return true;
};

export const initProgress = async () => {
  const local = loadSavedList<Quest>("hsCards");
  const server = await loadState();
  const fromServer = ALL_QUESTS.filter(quest => server?.[`${quest}_finished_at`]);

  cards = ALL_QUESTS.filter(quest => local.includes(quest) || fromServer.includes(quest));
  if (cards.length !== local.length) {
    await saveCards();
  }
  emit();
  return server;
};
