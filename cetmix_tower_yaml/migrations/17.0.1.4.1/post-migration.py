def migrate(cr, version):
    """
    Normalize existing license values to lowercase.
    Runs only on upgrade (version != False).
    """
    if not version:
        return
    # Skip rows already lowercase for efficiency
    cr.execute(
        """
        UPDATE cx_tower_yaml_manifest_tmpl
           SET license = LOWER(TRIM(license))
         WHERE license IS NOT NULL
           AND (
                license <> LOWER(license)
             OR license <> TRIM(license)
           )
    """
    )
