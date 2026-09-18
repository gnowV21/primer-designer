export const DEFAULTS = {
  sequence: {
    searchQuery:    '',
    mirnaName:      '',
    mirbaseId:      '',
    matureSequence: '',
    species:        'human',
    accession:      '',
    family:         '',
  },

  thermodynamic: {
    tmMin: 58,
    tmMax: 62,
    saltConcentration: 50,
    primerConcentration: 200,
    magnesiumConcentration: 1.5,
    dntpTotal: 0.8,
    kPlusConc: 50,
    bufferPH: 8.4,
  },

  primerConstraints: {
    gcMin: 40,
    gcMax: 60,
    lengthMin: 20,
    lengthMax: 27,
    gcClamp3prime: true,
    bindingRegion3prime: 6,
  },

  qpcr: {
    annealingTemp: 60,
    ampliconMin: 60,
    ampliconMax: 150,
    totalCycles: 40,
    pcrEfficiencyMin: 90,
    pcrEfficiencyMax: 110,
  },

  detectionMethod: {
    signalMethod: 'taqman',
    quantMode: 'relative',
    referenceGene: 'miR-16',
    customReferenceGene: '',
    enableFamilyDiscrimination: true,
    enablePrecursorCheck: false,
    enableRefoldingProtocol: true,
  },

  experimentalContext: {
    sampleType: 'tissue',
    qpcrSystem: 'other',
    rtEnzyme: 'mmlv',
    exportFormat: ['copy'],
    // Which designer produced the request: 'basic' (/design) or 'advanced'
    // (/design/advanced). Set by useDesignForm on submit; ResultsPage reads it to
    // decide whether the deep-science panels start collapsed. Does NOT affect the
    // algorithm. Defaults to 'advanced' so any caller that omits it sees the full
    // report rather than a trimmed one.
    userLevel: 'advanced',
  },
};

export const LIMITS = {
  thermodynamic: {
    tmMin: 50, tmMax: 70,
    saltMin: 1, saltMax: 500,
    primerConcMin: 50, primerConcMax: 1000,
    mgMin: 0.5, mgMax: 5.0,
    dntpMin: 0.2, dntpMax: 2.0,
    kPlusMin: 0, kPlusMax: 200,
    bufferPHMin: 7.0, bufferPHMax: 9.5,
  },
  primerConstraints: {
    gcMin: 20, gcMax: 80,
    lengthMin: 15, lengthMax: 27,
  },
  qpcr: {
    taMin: 50, taMax: 68,
    ampliconMin: 40, ampliconMax: 300,
    cyclesMin: 30, cyclesMax: 50,
    efficiencyMin: 80, efficiencyMax: 120,
  },
};

export const SPECIES_OPTIONS = [
  { value: 'human', label: 'Human',  scientific: 'Homo sapiens' },
  { value: 'mouse', label: 'Mouse',  scientific: 'Mus musculus' },
  { value: 'rat',   label: 'Rat',    scientific: 'Rattus norvegicus' },
  { value: 'other', label: 'Other',  scientific: 'Other species' },
];

export const SAMPLE_TYPE_PRESETS = {
  serum: {
    ampliconMax: 100,
    primerConcentration: 50,
    warning: 'Serum samples typically contain very low RNA levels. Shorter amplicons and an internal reference control (miR-16 or cel-miR-39 spike-in) are strongly recommended.',
  },
  plasma: {
    ampliconMax: 100,
    primerConcentration: 50,
    warning: 'Plasma is similar to serum. Note that anticoagulant type (EDTA vs heparin) may affect PCR efficiency — heparin can inhibit polymerase.',
  },
  ffpe: {
    ampliconMax: 80,
    ampliconMin: 60,
    warning: 'FFPE samples: RNA is cross-linked and fragmented by formalin fixation. Amplicons must be very short (60–80 bp). Thorough deparaffinization and RNA release steps are required before RT.',
  },
  tissue: {},
  cell: {},
  urine: {
    warning: 'Urine samples may contain PCR inhibitors (salts, urea). Consider a 1:5 dilution before RT and adding BSA to the master mix to sequester inhibitors.',
  },
};

export const QPCR_SYSTEM_NOTES = {
  abi:    'ABI/Applied Biosystems: ROX passive reference dye is required in the master mix. Use the correct ROX concentration for your instrument model (low ROX for 7500/7900, high ROX for StepOne/StepOnePlus).',
  biorad: 'Bio-Rad CFX: Do NOT use ROX. Use CFX-specific master mix (e.g. iTaq Universal SYBR/Probes). Normalization is handled automatically by CFX Manager software.',
  roche:  'Roche LightCycler: Uses capillary tubes. Smaller reaction volume (10–20 µl). FastStart master mix is optimized for this system.',
  qiagen: 'Qiagen Rotor-Gene: Spinning rotor format. No passive reference needed. QuantiTect or QuantiNova master mixes are recommended.',
  other:  'Consult your instrument manual for reference dye requirements, optimal reaction volume, and compatible master mixes.',
};

export const RT_ENZYME_NOTES = {
  mmlv:        { optimalTemp: '37–42°C', note: 'M-MLV RNase H+: the original RT enzyme. Works well at 37–42°C. Well-suited for standard stem-loop RT-qPCR protocols.' },
  superscript: { optimalTemp: '50–55°C', note: 'SuperScript III/IV (Thermo): thermostable at 50–55°C, reduces RNA secondary structure. Better yield for difficult or low-input samples.' },
  revertaid:   { optimalTemp: '42–50°C', note: 'RevertAid (Thermo): a balance between M-MLV and SuperScript. Good for routine samples.' },
  other:       { optimalTemp: 'See manufacturer datasheet', note: 'Check the optimal temperature of your RT enzyme before setting up the protocol.' },
};
