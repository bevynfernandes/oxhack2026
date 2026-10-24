# AndroidX attribution

The six spring parameter pairs in tokens.ts are adapted from
ExpressiveMotionTokens.kt, Copyright 2024 The Android Open Source Project,
licensed under Apache License 2.0 (LICENSE.txt in this directory).

Source revision: 53bc2d6eef5ae5438d07f0071dc6f698428df978, tokens version v0_14_0.
https://github.com/androidx/androidx/blob/53bc2d6eef5ae5438d07f0071dc6f698428df978/compose/material3/material3/src/commonMain/kotlin/androidx/compose/material3/tokens/ExpressiveMotionTokens.kt

Modifications: represented tokens in TypeScript and converted the damping ratio
into a unit-mass damping coefficient. AndroidX's rendering or simulation engine
is not copied. Motion for React executes the physical springs in the browser.
