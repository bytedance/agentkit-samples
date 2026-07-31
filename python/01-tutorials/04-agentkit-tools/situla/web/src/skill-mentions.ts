import type { SkillSummary } from "./types.js";

export interface ActiveSkillMention {
  start: number;
  query: string;
}

export interface SkillDisplayParts {
  content: string;
  skillNames: string[];
}

export interface ComposerSkillDisplay {
  content: string;
  skillNames: string[];
}

export function activeSkillMention(value: string): ActiveSkillMention | undefined {
  const match = value.match(/^\$([A-Za-z0-9._:-]*)$/u);
  if (!match) return undefined;
  return {
    start: 0,
    query: match[1],
  };
}

export function skillMenuItems(
  mention: ActiveSkillMention | undefined,
  skills: readonly SkillSummary[],
): SkillSummary[] {
  if (!mention) return [];
  const query = mention.query.toLowerCase();
  return skills
    .filter((skill) => {
      if (!query) return true;
      return `${skill.name} ${skill.description}`.toLowerCase().includes(query);
    })
    .sort((left, right) => {
      const score = skillScore(left, query) - skillScore(right, query);
      return score || left.name.localeCompare(right.name);
    })
    .slice(0, 12);
}

export function insertSkillMention(
  value: string,
  mention: ActiveSkillMention,
  skill: SkillSummary,
): string {
  return `${value.slice(0, mention.start)}$${skill.name} `;
}

export function skillIdsForText(
  value: string,
  skills: readonly SkillSummary[],
  preferredIds: ReadonlyMap<string, string> = new Map(),
): string[] {
  const skillsByName = new Map<string, SkillSummary[]>();
  for (const skill of skills) {
    const matches = skillsByName.get(skill.name) ?? [];
    matches.push(skill);
    skillsByName.set(skill.name, matches);
  }

  const ids: string[] = [];
  for (const name of leadingSkillNames(value, new Set(skillsByName.keys()))) {
    const matches = skillsByName.get(name) ?? [];
    const preferredId = preferredIds.get(name);
    const selected = matches.find((skill) => skill.id === preferredId) ?? matches[0];
    if (selected && !ids.includes(selected.id)) ids.push(selected.id);
    if (ids.length >= 20) break;
  }
  return ids;
}

export function skillDisplayParts(
  value: string,
  skillNames: readonly string[],
): SkillDisplayParts {
  const parsed = leadingSkillPrefix(value, new Set(skillNames));
  return {
    content: parsed.content,
    skillNames: parsed.skillNames,
  };
}

export function composerSkillDisplay(
  value: string,
  skillNames: readonly string[],
): ComposerSkillDisplay {
  let content = value;
  const allowedNames = new Set(skillNames);
  const leadingNames: string[] = [];
  while (content) {
    const name = leadingSkillName(content, allowedNames);
    if (!name || !/^\s/u.test(content.slice(name.length + 1))) break;
    content = content.slice(name.length + 1).replace(/^[\t ]+/u, "");
    if (!leadingNames.includes(name)) leadingNames.push(name);
  }
  return { content, skillNames: leadingNames };
}

export function composerValueWithSkills(
  content: string,
  skillNames: readonly string[],
): string {
  const prefix = [...new Set(skillNames)].map((name) => `$${name}`).join(" ");
  if (!prefix) return content;
  return content ? `${prefix} ${content}` : `${prefix} `;
}

function skillScore(skill: SkillSummary, query: string): number {
  if (!query) return 3;
  const name = skill.name.toLowerCase();
  if (name === query) return 0;
  if (name.startsWith(query)) return 1;
  if (name.includes(query)) return 2;
  return 3;
}

function leadingSkillNames(
  value: string,
  allowedNames: ReadonlySet<string>,
): string[] {
  return leadingSkillPrefix(value, allowedNames).skillNames;
}

function leadingSkillPrefix(
  value: string,
  allowedNames: ReadonlySet<string>,
): SkillDisplayParts {
  let content = value;
  const skillNames: string[] = [];
  while (content) {
    const name = leadingSkillName(content, allowedNames);
    if (!name) break;
    content = content.slice(name.length + 1);
    if (!skillNames.includes(name)) skillNames.push(name);
    if (!/^\s/u.test(content)) break;
    content = content.trimStart();
  }
  return { content, skillNames };
}

function leadingSkillName(
  value: string,
  allowedNames: ReadonlySet<string>,
): string | undefined {
  let matched: string | undefined;
  for (const name of allowedNames) {
    const marker = `$${name}`;
    if (!value.startsWith(marker)) continue;
    const next = value.slice(marker.length, marker.length + 1);
    if (next && !/[\s)\]},.!?;:，。！？；：]/u.test(next)) continue;
    if (!matched || name.length > matched.length) matched = name;
  }
  return matched;
}
