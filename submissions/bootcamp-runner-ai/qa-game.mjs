// Drive Bootcamp Runner into the game screen and report what the scene contains.
export default async function run(page, ui) {
  const menu = await ui.snapshot()

  // Start a run from the menu.
  const start = menu.match(/@(e\d+) button "Start a run[^"]*"/)
  if (!start) return { step: 'menu', error: 'no start button found', menu }
  await ui.click(start[1])
  await page.waitForTimeout(2500)

  const canvasInfo = await page.evaluate(() => {
    const c = document.querySelector('canvas')
    if (!c) return { canvas: false }
    const gl = c.getContext('webgl2') || c.getContext('webgl')
    return {
      canvas: true,
      width: c.width,
      height: c.height,
      cssWidth: c.clientWidth,
      cssHeight: c.clientHeight,
      hasGl: !!gl,
      glLost: gl ? gl.isContextLost() : null,
    }
  })

  const inGame = await page.evaluate(() => ({
    gameShell: !!document.querySelector('.game-shell'),
    hud: document.querySelector('.hud')?.innerText?.slice(0, 300) ?? null,
    question: document.querySelector('.question-panel')?.innerText?.slice(0, 300) ?? null,
    bodyText: document.body.innerText.slice(0, 400),
  }))

  return { step: 'game', canvasInfo, inGame }
}
