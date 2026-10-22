from .common import CommonTest


class TestServerYaml(CommonTest):
    """YAML import of a server that owns files."""

    def _server_with_file(self, name, server_dir):
        """Create a server and one file on it.

        Args:
            name (str): Server name.
            server_dir (str): Directory stored on the file.

        Returns:
            tuple: Server and its file.
        """
        server = self.Server.create(
            {
                "name": name,
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "os_id": self.os_debian_10.id,
            }
        )
        server_file = self.File.create(
            {
                "name": f"{name} file",
                "server_id": server.id,
                "source": "tower",
                "server_dir": server_dir,
            }
        )
        return server, server_file

    def _export(self, server):
        """Export one server.

        Args:
            server (cx.tower.server): Server to export.

        Returns:
            str: YAML code.
        """
        wizard = (
            self.env["cx.tower.yaml.export.wiz"]
            .with_context(active_model=server._name, active_ids=server.ids)
            .create({})
        )
        wizard.onchange_include_related_records()
        return wizard.yaml_code

    def _import(self, code, if_record_exists):
        """Import YAML in the given mode.

        Args:
            code (str): YAML code.
            if_record_exists (str): ``create`` or ``update``.

        Returns:
            dict: Import action.
        """
        importer = self.env["cx.tower.yaml.import.wiz"].create(
            {"if_record_exists": if_record_exists, "yaml_code": code}
        )
        return importer.action_import_yaml()

    def test_create_server_copy_keeps_files(self):
        """A copied server gets its own files and git project link."""
        server, server_file = self._server_with_file(
            "YAML File Server", "/opt/yaml-file-server"
        )
        relation = self.GitProjectRel.create(
            {
                "server_id": server.id,
                "file_id": server_file.id,
                "git_project_id": self.git_project_1.id,
                "project_format": "git_aggregator",
            }
        )
        self._import(self._export(server), "create")
        copies = self.Server.search(
            [("name", "=", server.name), ("id", "!=", server.id)]
        )
        self.assertEqual(server_file.server_id, server)
        self.assertEqual(server.file_ids, server_file)
        self.assertEqual(relation.file_id, server_file)
        self.assertEqual(relation.server_id, server)
        self.assertEqual(len(copies), 1)
        self.assertEqual(len(copies.file_ids), 1)
        self.assertNotEqual(copies.file_ids, server_file)
        self.assertEqual(copies.file_ids.server_dir, server_file.server_dir)
        self.assertEqual(len(copies.git_project_rel_ids), 1)
        self.assertEqual(copies.git_project_rel_ids.file_id, copies.file_ids)
        self.assertEqual(copies.git_project_rel_ids.git_project_id, self.git_project_1)
        self.assertNotEqual(copies.git_project_rel_ids, relation)

    def test_update_server_writes_existing_file(self):
        """Update writes the existing file and leaves it on the server."""
        server, server_file = self._server_with_file(
            "YAML File Server Update", "/opt/yaml-file-update"
        )
        code = self._export(server).replace(
            "/opt/yaml-file-update", "/opt/yaml-file-updated"
        )
        self._import(code, "update")
        self.assertEqual(server_file.server_id, server)
        self.assertEqual(server.file_ids, server_file)
        self.assertEqual(server_file.server_dir, "/opt/yaml-file-updated")
        self.assertEqual(self.Server.search_count([("name", "=", server.name)]), 1)
