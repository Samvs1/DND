// The shared screen follows the table's audio settings (M11.2 `state.audio`, set from any phone):
// each new value is copied into the screen's own settings, which narration.js and music.js read.
// The screen gear edits the same settings, so the last write wins. Decision logged in DECISIONS.md.
import { updateSettings } from '../settings/model.js';

export function bindRemoteAudio({ store, saved, mode }) {
  if (mode !== 'screen') return () => {};
  let last = null;
  return store.subscribe((state) => {
    const audio = state.snapshot?.state?.audio;
    const key = audio ? JSON.stringify(audio) : null;
    if (!audio || key === last) return;
    last = key;
    updateSettings(
      {
        narrationVolume: audio.narration_volume,
        musicVolume: audio.music_volume,
        mute: audio.narration_muted,
        muteSet: true,
        musicMute: audio.music_muted,
        musicMuteSet: true,
      },
      saved,
    );
  });
}
