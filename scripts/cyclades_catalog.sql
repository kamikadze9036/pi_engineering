-- Run from the Cyclades SQL Server context. These are read-only source queries.
-- Machines
SELECT MAC_REFMAC AS code, MAC_LIBMAC AS name
FROM SUIVPRO.dbo.MACHINE
WHERE MAC_REFMAC IS NOT NULL
ORDER BY MAC_REFMAC;

-- Injection tools/forms. LISTE_OUTILS is the live view documented in pi_cyclades.
SELECT OUT_REFOUT AS code, OUT_LIBOUT AS name, OUT_TYPEOUT AS tool_type
FROM SUIVPRO.dbo.LISTE_OUTILS
WHERE OUT_REFOUT LIKE 'MO%'
ORDER BY OUT_REFOUT;
