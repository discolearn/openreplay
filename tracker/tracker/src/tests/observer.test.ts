import TopObserver, { InlineCssMode } from '../main/app/observer/top_observer.js'
import Observer from '../main/app/observer/observer.js'
import { jest, expect, it, describe } from '@jest/globals'

describe('Observer inliner options', () => {
  const fakeApp = {
    nodes: {
      attachNodeCallback: jest.fn(),
      clear: jest.fn(),
      syntheticMode: jest.fn(),
      callNodeCallbacks: jest.fn(),
      registerNode: jest.fn(() => [1, true]),
      getID: jest.fn(() => 1),
      getNode: jest.fn(() => document.createElement('div')),
      unregisterNode: jest.fn(),
    },
    send: jest.fn(),
    debug: { warn: jest.fn(), info: jest.fn() },
    safe: (fn: any) => fn,
    sanitizer: { sanitize: jest.fn((id, data) => data), privateMode: false },
    attributeSender: { sendSetAttribute: jest.fn() },
    options: {},
  }

  it('should set inlinerOptions correctly for InlineCssMode.PlainFetched', () => {
    const topObs = new TopObserver({
      app: fakeApp as any,
      options: { inlineCss: InlineCssMode.PlainFetched },
    })
    // @ts-ignore
    expect(topObs['options'].inlineCss).toBe(InlineCssMode.PlainFetched)
    // @ts-ignore
    expect('inlineRemoteCss' in topObs).toBe(true)
    // @ts-ignore
    expect(topObs.inlinerOptions).toMatchObject({ forceFetch: true, forcePlain: true })
  })

  it('should pass inlinerOptions to Observer', () => {
    const obs = new (Observer as any)(fakeApp, true, {
      inlineRemoteCss: true,
      inlinerOptions: { forceFetch: true, forcePlain: true },
    })
    expect(obs.inlineRemoteCss).toBe(true)
    expect(obs.inlinerOptions).toMatchObject({ forceFetch: true, forcePlain: true })
  })
})
