# Controller offsets on Quest

[Back to the project](../README.md) · [Installation](WINDOWS.md) · [العربية](CONTROLLER-OFFSETS.ar.md)

This pack uses an experimental port of [CongXinJian](https://github.com/lixiangwuxian/CongXinJian) for per-hand saber position and rotation, three saved slots, **Auto Pos** and **Auto Rot**. It is a Quest alternative for controller adjustment; it does not reproduce PC EasyOffset's complete interface or Swing Benchmark features.

CongXinJian is included in the `recommended` profile as a **local-build package**. Follow the [Windows guide](WINDOWS.md) to build and install it. The pack supplies no personal grip settings.

## Open the controls

Open **Solo → CongXinJian** in the mods panel beside song selection. The general Mod Settings page contains language settings; calibration controls are in the Solo tab.

1. Enable the mod and select an **unused slot**. Use Slot 3 only if it is empty. If all three slots are in use, back up your mod settings before replacing one: releasing the calibration button saves the result to the selected slot.
2. For a manual check, choose **Left** or **Right** and make a small position or rotation adjustment while watching that saber. Restore the value if you were only testing the control.
3. Select **B/Y** as the calibration button to keep normal trigger clicks from starting calibration.

The calibration button is on the **opposite controller** from the saber being adjusted:

| Saber to adjust | Button to hold | Hand to move |
| --- | --- | --- |
| Right | **Y** on the left controller | Right hand |
| Left | **B** on the right controller | Left hand |

The **Left/Right** selector controls the manual fields. It does not change this opposite-hand button mapping.

## Auto Pos

Select **Auto Pos**. Hold the button from the table, keep the wrist of the hand being calibrated in roughly the same place, and rotate that hand through several different directions. Release the button to save the result.

Keeping the hand completely still or rotating around only one axis does not provide enough information for a useful position estimate. Check the result visually and with a comfortable swing; repeat on the other hand separately.

## Auto Rot

Select **Auto Rot**. While holding the opposite controller's button, rotate the hand being calibrated around the direction in which you want the saber to extend. Release the button, inspect the result and test it gently. Each hand may need a different adjustment because grips differ.

Calibrate in the menu where you can see the saber. Tracking loss or a change of slot/mode during calibration cancels that attempt and restores the values from before the button was pressed. Do not assume a completed calculation is a suitable grip: check how it feels and retain your previous slot if it is better.

## What has actually been checked

The original local v5 build passed a bounded Quest 3 startup check after a startup crash was fixed. Manual adjustment was tested on Beat Saber 1.45.1, and a user confirmed that **Auto Pos direction and position were correct**. Auto Rot recorded completed trials, and both gameplay sabers were detected.

**User confirmation of Auto Rot quality and calibration after returning from gameplay remains pending.** Menu/gameplay transitions have host logic tests, which do not replace headset testing. The portable build produced by this repository has not itself been validated on a headset, even though its source derives from that local port. See [the release validation notes](VALIDATION.md).

If calibration looks wrong, record the mode, hand, button, and whether the issue happens before or after playing a song. Preserve your previous settings; do not copy somebody else's numbers as personal calibration.
