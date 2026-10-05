// Maps a server creation-error field name to the wizard step that owns it.

/** Which step a server creation error belongs to, by its field name. */
export function stepForField(field, ctx) {
  const root = field.split('.')[0];
  const second = field.split('.')[1];
  if (['race', 'subrace', 'ability_choice_picks', 'tool_picks', 'language_picks'].includes(root)) return 'race';
  if (['class_index', 'class_choices'].includes(root)) return 'class';
  if (root === 'background') return 'background';
  if (['base_scores', 'rolls'].includes(root)) return 'abilities';
  if (['class_skills', 'race_skills', 'skills'].includes(root)) return 'skills';
  if (root === 'equipment_picks') return 'equipment';
  if (['cantrips', 'race_cantrips', 'spells', 'prepared'].includes(root)) return 'spells';
  if (root === 'portrait_id') return 'portrait';
  if (['name', 'pronouns', 'backstory'].includes(root)) return 'identity';
  if (root === 'feature_choices') {
    if ((ctx.cls?.expertise ?? []).some((e) => e.id === second)) return 'skills';
    return (ctx.cls?.feature_picks ?? []).some((p) => p.id === second) ? 'class' : 'race';
  }
  return 'review';
}
