import { describe, expect, it } from 'vitest'
import { translateServerText, translateVoicePresetName } from './i18n'

describe('i18n translations', () => {
  it('translates common backend job stages to English', () => {
    expect(translateServerText('正在渲染视频帧与音频', 'en')).toBe('Rendering video frames and audio')
    expect(translateServerText('视频已生成：demo.mp4', 'en')).toBe('Video generated: demo.mp4')
  })

  it('keeps Chinese backend text in Chinese mode', () => {
    expect(translateServerText('正在准备 TTS', 'zh')).toBe('正在准备 TTS')
  })

  it('translates built-in voice preset labels without changing IDs', () => {
    expect(translateVoicePresetName('女性温暖', 'en')).toBe('Female warm')
    expect(translateVoicePresetName('女性温暖', 'zh')).toBe('女性温暖')
  })
})
