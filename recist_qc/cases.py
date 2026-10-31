"""Synthetic fixtures with independently specified expected outcomes."""

CASES = [{'id': '01_clean',
  'label': 'Clean data',
  'csv': 'patient_id,visit,assessment_date,lesion_id,organ,lesion_type,is_target,diameter_mm\n'
         'SYNTHETIC-101,baseline,2026-01-01,L1,lung,non_nodal,yes,20\n'
         'SYNTHETIC-101,baseline,2026-01-01,L2,lymph_nodes,nodal,yes,15\n'
         'SYNTHETIC-101,week_6,2026-02-12,L1,lung,non_nodal,yes,0\n'
         'SYNTHETIC-101,week_6,2026-02-12,L2,lymph_nodes,nodal,yes,9\n',
  'expected': {'rows_checked': 4, 'errors': 0, 'warnings': 0, 'codes': {}}},
 {'id': '02_invalid_values',
  'label': 'Invalid values',
  'csv': 'patient_id,visit,assessment_date,lesion_id,organ,lesion_type,is_target,diameter_mm\n'
         'SYNTHETIC-201,baseline,2026-01-01,L1,lung,non_nodal,no,-5\n'
         'SYNTHETIC-202,baseline,2026-01-01,L1,lung,non_nodal,maybe,20\n'
         'SYNTHETIC-203,baseline,2026-02-30,L1,lung,non_nodal,no,20\n'
         'SYNTHETIC-204,baseline,2026-01-01,L1,lung,unknown,no,20\n'
         'SYNTHETIC-205,baseline,2026-01-01,L1,lung,non_nodal,no,NaN\n'
         'SYNTHETIC-206,baseline,2026-01-01,L1,,non_nodal,yes,20\n',
  'expected': {'rows_checked': 6,
               'errors': 6,
               'warnings': 0,
               'codes': {'INVALID_DIAMETER': 2,
                         'INVALID_TARGET': 1,
                         'INVALID_DATE': 1,
                         'INVALID_LESION_TYPE': 1,
                         'REQUIRED_VALUE': 1}}},
 {'id': '03_too_many_targets',
  'label': 'Too many baseline targets',
  'csv': 'patient_id,visit,assessment_date,lesion_id,organ,lesion_type,is_target,diameter_mm\n'
         'SYNTHETIC-301,baseline,2026-01-01,L1,lung,non_nodal,yes,20\n'
         'SYNTHETIC-301,baseline,2026-01-01,L2,lung,non_nodal,yes,20\n'
         'SYNTHETIC-301,baseline,2026-01-01,L3,lung,non_nodal,yes,20\n'
         'SYNTHETIC-301,baseline,2026-01-01,L4,liver,non_nodal,yes,20\n'
         'SYNTHETIC-301,baseline,2026-01-01,L5,liver,non_nodal,yes,20\n'
         'SYNTHETIC-301,baseline,2026-01-01,L6,kidney,non_nodal,yes,20\n',
  'expected': {'rows_checked': 6,
               'errors': 0,
               'warnings': 2,
               'codes': {'TARGET_COUNT': 1, 'ORGAN_TARGET_COUNT': 1}}},
 {'id': '04_changes_across_visits',
  'label': 'Changes across visits',
  'csv': 'patient_id,visit,assessment_date,lesion_id,organ,lesion_type,is_target,diameter_mm\n'
         'SYNTHETIC-401,baseline,2026-01-01,L1,lung,non_nodal,yes,20\n'
         'SYNTHETIC-401,week_6,2026-02-12,L1,liver,non_nodal,yes,20\n'
         'SYNTHETIC-401,week_6,2026-02-13,L2,lung,non_nodal,no,20\n',
  'expected': {'rows_checked': 3,
               'errors': 0,
               'warnings': 2,
               'codes': {'LESION_CHANGED': 1, 'VISIT_DATE_MISMATCH': 1}}},
 {'id': '05_small_baseline_targets',
  'label': 'Small baseline targets',
  'csv': 'patient_id,visit,assessment_date,lesion_id,organ,lesion_type,is_target,diameter_mm\n'
         'SYNTHETIC-501,baseline,2026-01-01,L1,lung,non_nodal,yes,9\n'
         'SYNTHETIC-501,baseline,2026-01-01,L2,lymph_nodes,nodal,yes,14\n',
  'expected': {'rows_checked': 2,
               'errors': 0,
               'warnings': 2,
               'codes': {'BASELINE_TARGET_SIZE': 2}}},
 {'id': '06_duplicate_records',
  'label': 'Duplicate records',
  'csv': 'patient_id,visit,assessment_date,lesion_id,organ,lesion_type,is_target,diameter_mm\n'
         'SYNTHETIC-601,baseline,2026-01-01,L1,lung,non_nodal,yes,20\n'
         'SYNTHETIC-601,baseline,2026-01-01,L1,lung,non_nodal,yes,20\n',
  'expected': {'rows_checked': 2, 'errors': 1, 'warnings': 0, 'codes': {'DUPLICATE_LESION': 1}}}]
