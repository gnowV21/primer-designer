#!/usr/bin/env python3
"""
Seed the local SQLite DB with a curated set of frequently studied miRNAs.
Run this when miRBase.org is unreachable or as a quick offline bootstrap.

All sequences are from miRBase release 22.1 (https://mirbase.org).
Run build_db.py to replace this with the full ~38,000-entry miRBase release.

Usage: python scripts/seed_db.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from db import local_db

# fmt: off
# (name, accession, sequence, family, species)
SEED = [

    # ── Homo sapiens — oncomiRs & tumour suppressors ───────────────────────
    ("hsa-miR-21-5p",    "MIMAT0000076", "UAGCUUAUCAGACUGAUGUUGA",    "MIR21",    "Homo sapiens"),
    ("hsa-miR-21-3p",    "MIMAT0000077", "AAGCUGCCAGUUGAAGAACUGU",    "MIR21",    "Homo sapiens"),
    ("hsa-miR-155-5p",   "MIMAT0000646", "UUAAUGCUAAUUGUGAUAGGGGU",   "MIR155",   "Homo sapiens"),
    ("hsa-miR-155-3p",   "MIMAT0004658", "CUCCUACAUAUUAGCAUUAACA",    "MIR155",   "Homo sapiens"),
    ("hsa-miR-210-3p",   "MIMAT0000267", "CUGUGCGUGUGACAGCGGCUGA",    "MIR210",   "Homo sapiens"),
    ("hsa-miR-10b-5p",   "MIMAT0000254", "UACCCUGUAGAACCGAAUUUGUG",   "MIR10",    "Homo sapiens"),
    ("hsa-miR-10b-3p",   "MIMAT0004556", "ACAGAUUCGAUUCUAGGGGAAU",    "MIR10",    "Homo sapiens"),

    # ── let-7 family (Homo sapiens) ────────────────────────────────────────
    ("hsa-let-7a-5p",    "MIMAT0000062", "UGAGGUAGUAGGUUGUAUAGUU",    "MIRLET7",  "Homo sapiens"),
    ("hsa-let-7a-3p",    "MIMAT0004481", "CUAUACAAUCUACUGUCUUUC",     "MIRLET7",  "Homo sapiens"),
    ("hsa-let-7b-5p",    "MIMAT0000063", "UGAGGUAGUAGGUUGUGUGGUU",    "MIRLET7",  "Homo sapiens"),
    ("hsa-let-7c-5p",    "MIMAT0000064", "UGAGGUAGUAGGUUGUAUGGUU",    "MIRLET7",  "Homo sapiens"),
    ("hsa-let-7d-5p",    "MIMAT0000065", "AGAGGUAGUAGGUUGCAUAGU",     "MIRLET7",  "Homo sapiens"),
    ("hsa-let-7e-5p",    "MIMAT0000066", "UGAGGUAGGAGGUUGUAUAGU",     "MIRLET7",  "Homo sapiens"),
    ("hsa-let-7f-5p",    "MIMAT0000067", "UGAGGUAGUAGAUUGUAUAGUU",    "MIRLET7",  "Homo sapiens"),
    ("hsa-let-7g-5p",    "MIMAT0000414", "UGAGGUAGUAGUUUGUACAGU",     "MIRLET7",  "Homo sapiens"),
    ("hsa-let-7i-5p",    "MIMAT0000415", "UGAGGUAGUAGUUUGUGCU",       "MIRLET7",  "Homo sapiens"),

    # ── miR-17-92 cluster (oncomiR-1) ─────────────────────────────────────
    ("hsa-miR-17-5p",    "MIMAT0000070", "CAAAGUGCUUACAGUGCAGGUAG",   "MIR17",    "Homo sapiens"),
    ("hsa-miR-17-3p",    "MIMAT0000071", "ACUGCAGUGAAGGCACUUGUGAG",   "MIR17",    "Homo sapiens"),
    ("hsa-miR-18a-5p",   "MIMAT0000072", "UAAGGUGCAUCUAGUGCAGAUAG",   "MIR18",    "Homo sapiens"),
    ("hsa-miR-19a-3p",   "MIMAT0000073", "UGUGCAAAUCUAUGCAAAACUGA",   "MIR17",    "Homo sapiens"),
    ("hsa-miR-19b-3p",   "MIMAT0000074", "UGUGCAAAUCCAUGCAAAACUGA",   "MIR17",    "Homo sapiens"),
    ("hsa-miR-20a-5p",   "MIMAT0000075", "UAAAGUGCUUAUAGUGCAGGUAG",   "MIR17",    "Homo sapiens"),
    ("hsa-miR-92a-3p",   "MIMAT0000092", "UAUUGCACUUGUCCCGGCCUGU",    "MIRLET7",  "Homo sapiens"),
    ("hsa-miR-93-5p",    "MIMAT0000093", "CAAAGUGCUGUUCGUGCAGGUAG",   "MIR17",    "Homo sapiens"),

    # ── miR-16/15 family (tumour suppressors, CLL) ────────────────────────
    ("hsa-miR-15a-5p",   "MIMAT0000068", "UAGCAGCACAUAAUGGUUUGUG",    "MIR15",    "Homo sapiens"),
    ("hsa-miR-15a-3p",   "MIMAT0004490", "ACAAACCACACUGUGGUAAUGAA",   "MIR15",    "Homo sapiens"),
    ("hsa-miR-15b-5p",   "MIMAT0000417", "UAGCAGCACAUCAUGGUUUACA",    "MIR15",    "Homo sapiens"),
    ("hsa-miR-16-5p",    "MIMAT0000069", "UAGCAGCACGUAAAUAUUGGCG",    "MIR16",    "Homo sapiens"),
    ("hsa-miR-16-1-3p",  "MIMAT0004489", "CCAGUAUUGACUUAAAUACUUU",    "MIR16",    "Homo sapiens"),
    ("hsa-miR-195-5p",   "MIMAT0000461", "UAGCAGCACAGAAAUAUUGGC",     "MIR15",    "Homo sapiens"),

    # ── miR-34 family (p53-regulated) ─────────────────────────────────────
    ("hsa-miR-34a-5p",   "MIMAT0000255", "UGGCAGUGUCUUAGCUGGUUGU",    "MIR34",    "Homo sapiens"),
    ("hsa-miR-34a-3p",   "MIMAT0004557", "CAAUCAGCAAGUAUACUGCCCU",    "MIR34",    "Homo sapiens"),
    ("hsa-miR-34b-5p",   "MIMAT0000685", "AGGCAGUGUCUUAGCUGAUUUC",    "MIR34",    "Homo sapiens"),
    ("hsa-miR-34c-5p",   "MIMAT0000686", "AGGCAGUGUCUUAGCUGGUUGU",    "MIR34",    "Homo sapiens"),

    # ── miR-200 family (EMT regulators) ───────────────────────────────────
    ("hsa-miR-200a-3p",  "MIMAT0000682", "UAACACUGCCUGGUAAUGAUGA",    "MIR200",   "Homo sapiens"),
    ("hsa-miR-200b-3p",  "MIMAT0000318", "UAAUACUGCCUGGUAAUGAUGA",    "MIR200",   "Homo sapiens"),
    ("hsa-miR-200c-3p",  "MIMAT0000617", "UAAUACUGCCGGGUAAUGAUGGA",   "MIR200",   "Homo sapiens"),
    ("hsa-miR-141-3p",   "MIMAT0000432", "UAACACUGUCUGGUAAAGAUGG",    "MIR200",   "Homo sapiens"),
    ("hsa-miR-429",      "MIMAT0001536", "UAAUACUGUCUGGUAAAACCGU",    "MIR200",   "Homo sapiens"),

    # ── Cardiac & muscle miRNAs ────────────────────────────────────────────
    ("hsa-miR-1-3p",     "MIMAT0000416", "UGGAAUGUAAAGAAGUAUGUAU",    "MIR1",     "Homo sapiens"),
    ("hsa-miR-133a-3p",  "MIMAT0000427", "UUUGGUCCCCUUCAACCAGCUG",    "MIR133",   "Homo sapiens"),
    ("hsa-miR-133a-5p",  "MIMAT0004567", "ACAGCUGGUGAGGGUGGGACU",     "MIR133",   "Homo sapiens"),
    ("hsa-miR-133b",     "MIMAT0000770", "UUUGGUCCCCUUCAACCAGCUA",    "MIR133",   "Homo sapiens"),
    ("hsa-miR-206",      "MIMAT0000462", "UGGAAUGUAAGGAAGUGUGUGG",    "MIR206",   "Homo sapiens"),
    ("hsa-miR-208a-3p",  "MIMAT0000431", "AUAAGACGAACAAAAGGUUUGU",    "MIR208",   "Homo sapiens"),

    # ── Liver & metabolic miRNAs ───────────────────────────────────────────
    ("hsa-miR-122-5p",   "MIMAT0000421", "UGGAGUGUGACAAUGGUGUUUG",    "MIR122",   "Homo sapiens"),
    ("hsa-miR-122-3p",   "MIMAT0004590", "CAAACACCAUUGUCACACUCCA",    "MIR122",   "Homo sapiens"),
    ("hsa-miR-375",      "MIMAT0000728", "UUUGUUCGUUCGGCUCGCGUGA",    "MIR375",   "Homo sapiens"),

    # ── Immune & inflammatory miRNAs ──────────────────────────────────────
    ("hsa-miR-146a-5p",  "MIMAT0000449", "UGAGAACUGAAUUCCAUGGGUU",    "MIR146",   "Homo sapiens"),
    ("hsa-miR-146a-3p",  "MIMAT0004559", "UGAGAACUGAAUUCCAUAGCCU",    "MIR146",   "Homo sapiens"),
    ("hsa-miR-146b-5p",  "MIMAT0002809", "UGAGAACUGAAUUCCAUAGGCU",    "MIR146",   "Homo sapiens"),
    ("hsa-miR-150-5p",   "MIMAT0000438", "UCUCCCAACCCUUGUACCAGUG",    "MIR150",   "Homo sapiens"),
    ("hsa-miR-223-3p",   "MIMAT0000280", "UGUCAGUUUGUCAAAUACCCCA",    "MIR223",   "Homo sapiens"),
    ("hsa-miR-223-5p",   "MIMAT0004570", "CGUGUAUUUGACAAGCUGAGUU",    "MIR223",   "Homo sapiens"),

    # ── Neuronal miRNAs ────────────────────────────────────────────────────
    ("hsa-miR-9-5p",     "MIMAT0000441", "UCUUUGGUUAUCUAGCUGUAUGA",   "MIR9",     "Homo sapiens"),
    ("hsa-miR-9-3p",     "MIMAT0000442", "UAAAGCUAGAUAACCGAAAGU",     "MIR9",     "Homo sapiens"),
    ("hsa-miR-132-3p",   "MIMAT0000426", "UAACAGUCUACAGCCAUGGUCG",    "MIR132",   "Homo sapiens"),
    ("hsa-miR-132-5p",   "MIMAT0000427", "ACCGUGGCUUUCGAUUGUUACU",    "MIR132",   "Homo sapiens"),
    ("hsa-miR-134-5p",   "MIMAT0000447", "UGUGACUGGUUGACCAGAGGGG",    "MIR134",   "Homo sapiens"),
    ("hsa-miR-137",      "MIMAT0000429", "UUAUUGCUUAAGAAUACGCGUAG",   "MIR137",   "Homo sapiens"),

    # ── Angiogenesis & hypoxia ────────────────────────────────────────────
    ("hsa-miR-126-3p",   "MIMAT0000445", "UCGUACCGUGAGUAAUAAUGCG",    "MIR126",   "Homo sapiens"),
    ("hsa-miR-126-5p",   "MIMAT0000444", "CAUUAUUACUUUUGGUACGCG",     "MIR126",   "Homo sapiens"),

    # ── Circulating & reference miRNAs ────────────────────────────────────
    ("hsa-miR-181a-5p",  "MIMAT0000256", "AACAUUCAACGCUGUCGGUGAGU",   "MIR181",   "Homo sapiens"),
    ("hsa-miR-181a-3p",  "MIMAT0000257", "ACCAUCGACCGUUGAUUGUACC",    "MIR181",   "Homo sapiens"),
    ("hsa-miR-205-5p",   "MIMAT0000266", "UCCUUCAUUCCACCGGAGUCUG",    "MIR205",   "Homo sapiens"),
    ("hsa-miR-451a",     "MIMAT0001520", "AAACCGUUACCAUUACUGAGUUU",   "MIR451",   "Homo sapiens"),
    ("hsa-miR-103a-3p",  "MIMAT0000101", "AGCAGCAUUGUACAGGGCUAUGA",   "MIR103",   "Homo sapiens"),
    ("hsa-miR-143-3p",   "MIMAT0000435", "UGAGAUGAAGCACUGUAGCUC",     "MIR143",   "Homo sapiens"),
    ("hsa-miR-145-5p",   "MIMAT0000437", "GUCCAGUUUUCCCAGGAAUCCCU",   "MIR145",   "Homo sapiens"),
    ("hsa-miR-145-3p",   "MIMAT0004601", "AGGGAUUUCUGAAACAUACUU",     "MIR145",   "Homo sapiens"),

    # ── Mouse orthologs ────────────────────────────────────────────────────
    ("mmu-miR-21a-5p",   "MIMAT0000530", "UAGCUUAUCAGACUGAUGUUGA",    "MIR21",    "Mus musculus"),
    ("mmu-let-7a-5p",    "MIMAT0000521", "UGAGGUAGUAGGUUGUAUAGUU",    "MIRLET7",  "Mus musculus"),
    ("mmu-miR-122-5p",   "MIMAT0000140", "UGGAGUGUGACAAUGGUGUUUG",    "MIR122",   "Mus musculus"),
    ("mmu-miR-155-5p",   "MIMAT0000165", "UUAAUGCUAAUUGUGAUAGGGGU",   "MIR155",   "Mus musculus"),
    ("mmu-miR-16-5p",    "MIMAT0000527", "UAGCAGCACGUAAAUAUUGGCG",    "MIR16",    "Mus musculus"),
    ("mmu-miR-146a-5p",  "MIMAT0000158", "UGAGAACUGAAUUCCAUGGGUU",    "MIR146",   "Mus musculus"),
    ("mmu-miR-9-5p",     "MIMAT0000142", "UCUUUGGUUAUCUAGCUGUAUGA",   "MIR9",     "Mus musculus"),
    ("mmu-miR-34a-5p",   "MIMAT0000542", "UGGCAGUGUCUUAGCUGGUUGU",    "MIR34",    "Mus musculus"),
    ("mmu-miR-1a-3p",    "MIMAT0000128", "UGGAAUGUAAAGAAGUAUGUAU",    "MIR1",     "Mus musculus"),
    ("mmu-miR-133a-3p",  "MIMAT0000135", "UUUGGUCCCCUUCAACCAGCUG",    "MIR133",   "Mus musculus"),
    ("mmu-miR-206-3p",   "MIMAT0000161", "UGGAAUGUAAGGAAGUGUGUGG",    "MIR206",   "Mus musculus"),

    # ── Rattus norvegicus orthologs ────────────────────────────────────────
    ("rno-miR-21-5p",    "MIMAT0000790", "UAGCUUAUCAGACUGAUGUUGA",    "MIR21",    "Rattus norvegicus"),
    ("rno-let-7a-5p",    "MIMAT0000774", "UGAGGUAGUAGGUUGUAUAGUU",    "MIRLET7",  "Rattus norvegicus"),
    ("rno-miR-122-5p",   "MIMAT0000829", "UGGAGUGUGACAAUGGUGUUUG",    "MIR122",   "Rattus norvegicus"),
    ("rno-miR-16-5p",    "MIMAT0000779", "UAGCAGCACGUAAAUAUUGGCG",    "MIR16",    "Rattus norvegicus"),
]
# fmt: on


def main():
    local_db.init_schema()
    count = 0
    for name, acc, seq, family, species in SEED:
        local_db.upsert({
            "id":        name,
            "accession": acc,
            "sequence":  seq,
            "family":    family,
            "species":   species,
            "length":    len(seq),
        })
        count += 1
    print(f"Seeded {count} miRNAs into {local_db.DB_PATH}")
    print("Run build_db.py to replace with the full miRBase release (~38,000 entries).")


if __name__ == '__main__':
    main()
