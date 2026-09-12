# Package Adjustment NextGen V2 — Prospective Activation UI Repair V1

The first prospective activation commit accidentally removed shared KTC browser helpers. This repair restores that shared block byte-for-byte from the immediate pre-activation parent while retaining the frozen prospective catalog, sampler, transport namespace, and original valid-ballot cutoff.

An outcome-blind audit found **zero prospective rows before repair**, so no prospective evidence was collected under the broken UI. Production V1.6 is unchanged.
