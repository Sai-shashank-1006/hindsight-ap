// The PaySage mascot's states. Each situation in the app picks one, so the mascot tells the story:
// confident → curious → puzzled → investigating → alarmed → asking the human → learning → confident.
// Lines only claim what the system really does: it checks prices and quantities against the PO,
// recalls human decisions from Hindsight, and stores decisions (not rules).

import type { Decision, InvoiceException, RecommendationResult, StoreDecisionResponse } from '../types';

/** The drawn poses available (src/assets/mascot/*.webp). */
export type MascotPose = 'thinking' | 'processing' | 'puzzled' | 'alarmed' | 'resolved' | 'wise' | 'calm';
export type MascotTone = 'teal' | 'blue' | 'violet' | 'amber' | 'red' | 'emerald';

export interface MascotState {
  pose: MascotPose;
  tone: MascotTone;
  title: string; // a short label for the situation
  line: string; // what the mascot says
}

export const MASCOT_STATES = {
  ready: { pose: 'thinking', tone: 'blue', title: 'Ready', line: 'Let’s see what this invoice is hiding…' },
  processing: { pose: 'processing', tone: 'teal', title: 'Processing invoice', line: 'Let’s see what this invoice is hiding…' },
  checkingRules: {
    pose: 'thinking',
    tone: 'blue',
    title: 'Checking the PO',
    line: 'Checking the price and quantity against the purchase order…',
  },
  searchingMemory: { pose: 'wise', tone: 'amber', title: 'Searching Hindsight', line: 'Wait… let me check what happened last time.' },
  exceptionDetected: { pose: 'alarmed', tone: 'red', title: 'Exception detected', line: 'Whoa! This invoice doesn’t match the purchase order.' },
  smallDifference: { pose: 'puzzled', tone: 'violet', title: 'Small difference', line: 'Hmm… a small difference from the purchase order.' },
  matchesPo: {
    pose: 'resolved',
    tone: 'emerald',
    title: 'Matches the PO',
    line: 'Everything matches the purchase order. It just needs your confirmation.',
  },
  unusual: { pose: 'puzzled', tone: 'violet', title: 'Something unusual', line: 'Hmm… this looks different from what I remember.' },
  riskyUnknown: { pose: 'alarmed', tone: 'red', title: 'No verified history', line: 'I don’t know this pattern yet. Better check with you.' },
  knownException: { pose: 'calm', tone: 'blue', title: 'Known exception', line: 'I’ve seen this before. Here’s what happened last time.' },
  recommendApproval: {
    pose: 'resolved',
    tone: 'emerald',
    title: 'Recommendation',
    line: 'I’ve seen this before. Based on verified history, I recommend approval.',
  },
  knownRejection: {
    pose: 'thinking',
    tone: 'red',
    title: 'Known rejection',
    line: 'I’ve seen this before, and a reviewer rejected it last time.',
  },
  needsReview: {
    pose: 'puzzled',
    tone: 'amber',
    title: 'Needs human review',
    line: 'My past decisions disagree on this one. I need your judgment.',
  },
  memoryOffline: {
    pose: 'puzzled',
    tone: 'amber',
    title: 'Memory offline',
    line: 'I can’t reach my memory right now, so I haven’t checked any history. Let’s review this together.',
  },
  humanCorrects: { pose: 'thinking', tone: 'violet', title: 'Human correction', line: 'Got it. I’ll remember why you made that decision.' },
  retaining: { pose: 'wise', tone: 'violet', title: 'Learning', line: 'Memory saved. I’ll remember this for next time.' },
  resolvedNothingToLearn: {
    pose: 'resolved',
    tone: 'emerald',
    title: 'Resolved',
    line: 'Solved. It matched the PO, so there’s nothing new to learn.',
  },
  notRemembered: {
    pose: 'puzzled',
    tone: 'amber',
    title: 'Not remembered',
    line: 'I couldn’t save that to memory. Let’s try again once it’s reachable.',
  },
  smarter: { pose: 'wise', tone: 'violet', title: 'Smarter over time', line: 'Every decision makes me a little wiser.' },
  firstDay: { pose: 'calm', tone: 'teal', title: 'Ready to learn', line: 'I don’t know your vendors yet. Every decision you make teaches me.' },
  emptyQueue: { pose: 'thinking', tone: 'blue', title: 'Nothing queued', line: 'No invoices waiting. Enter one and I’ll take a look.' },
  lost: { pose: 'puzzled', tone: 'violet', title: 'Page not found', line: 'Hmm… I don’t remember a page like this.' },
} satisfies Record<string, MascotState>;

export type MascotStateId = keyof typeof MASCOT_STATES;

/** While /process runs: the pipeline's steps, in the order they really happen. Stops on the last. */
export const PROCESSING_NARRATION: MascotStateId[] = ['processing', 'checkingRules', 'searchingMemory'];

/** What the rule engine found. */
export function stateForExceptions(exceptions: InvoiceException[]): MascotStateId {
  if (exceptions.length === 0) return 'matchesPo';
  return exceptions.some((exception) => exception.severity !== 'INFO') ? 'exceptionDetected' : 'smallDifference';
}

/** The agent's overall read of an invoice: memory first, because that's what the evidence rule uses. */
export function stateForResult(result: RecommendationResult): MascotStateId {
  if (result.exceptions.length === 0) return 'matchesPo';
  if (result.memory_status === 'unavailable') return 'memoryOffline';
  switch (result.evidence_level) {
    case 'VERIFIED_MATCH':
      return result.recommendation === 'APPROVED' ? 'recommendApproval' : 'knownException';
    case 'VERIFIED_REJECT':
      return 'knownRejection';
    case 'CONFLICT':
      return 'needsReview';
    default:
      // Memories exist but none matches this amount (e.g. a price that drifted again).
      return result.hindsight_memories.length > 0 ? 'unusual' : 'riskyUnknown';
  }
}

/** After the human decides. */
export function stateForOutcome(outcome: StoreDecisionResponse, decided: Decision | null, recommendation: Decision): MascotStateId {
  if (!outcome.success) return 'notRemembered';
  if (!outcome.retained) return 'resolvedNothingToLearn';
  return decided && decided !== recommendation ? 'humanCorrects' : 'retaining';
}
