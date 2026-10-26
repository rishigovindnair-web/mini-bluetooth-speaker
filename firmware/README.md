# Firmware

**This design has no firmware to write or flash.**

The only active electronics are two off-the-shelf modules, and neither runs code you supply:

- **MH-M38 Bluetooth amplifier** (sold by DFRobot as DFR0720): the Bluetooth stack, audio decoding
  and the 2 x 5 W amplifier are fixed in the module. Nothing in the maker documentation I found
  describes reflashing it. It starts in pairing mode on power-up and auto-reconnects. Depending on
  the seller it advertises as `MH-M38` or `XWF-M18-M28-M38`.
- **TP4056 Type-C module**: a hardware charger plus protection IC pair (DW01A + 8205A). It has no
  processor.

So there is no microcontroller, no bootloader, and no source to publish. A `firmware/` folder is here
only so nobody goes looking for one.

## If you want features that need firmware

The current design has none of these; adding any of them means adding a microcontroller (and
its cost, board space and wiring), which is outside this design:

- an auto-off timer (the slide switch already handles on/off)
- a battery-level indicator
- status LEDs

If you add one, put its source in this folder.
