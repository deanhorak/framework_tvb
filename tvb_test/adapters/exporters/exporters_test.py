# -*- coding: utf-8 -*-
#
#
# TheVirtualBrain-Framework Package. This package holds all Data Management, and 
# Web-UI helpful to run brain-simulations. To use it, you also need do download
# TheVirtualBrain-Scientific Package (for simulators). See content of the
# documentation-folder for more details. See also http://www.thevirtualbrain.org
#
# (c) 2012-2013, Baycrest Centre for Geriatric Care ("Baycrest")
#
# This program is free software; you can redistribute it and/or modify it under 
# the terms of the GNU General Public License version 2 as published by the Free
# Software Foundation. This program is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of 
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public
# License for more details. You should have received a copy of the GNU General 
# Public License along with this program; if not, you can download it here
# http://www.gnu.org/licenses/old-licenses/gpl-2.0
#
#
#   CITATION:
# When using The Virtual Brain for scientific publications, please cite it as follows:
#
#   Paula Sanz Leon, Stuart A. Knock, M. Marmaduke Woodman, Lia Domide,
#   Jochen Mersmann, Anthony R. McIntosh, Viktor Jirsa (2013)
#       The Virtual Brain: a simulator of primate brain network dynamics.
#   Frontiers in Neuroinformatics (in press)
#
#

"""
.. moduleauthor:: calin.pavel <calin.pavel@codemart.ro>
"""
import unittest
import os.path
import shutil
import zipfile
from contextlib import closing
from tvb.core.entities.storage import dao
from tvb.core.entities.file.fileshelper import FilesHelper
from tvb.adapters.exporters.export_manager import ExportManager
from tvb.adapters.exporters.exceptions import ExportException, InvalidExportDataException
from tvb_test.datatypes.datatypes_factory import DatatypesFactory
from tvb.basic.config.settings import TVBSettings as cfg
from tvb_test.core.base_testcase import TransactionalTestCase



class ExportersTest(TransactionalTestCase):
    """
    Test export functionality.
    """
    TVB_EXPORTER = "TVBExporter"
    CIFTI_EXPORTER = "CIFTIExporter"
    
    def setUp(self):
        self.export_manager = ExportManager()
        self.datatypeFactory = DatatypesFactory()
        self.project = self.datatypeFactory.get_project()
        
    def tearDown(self):
        """
        Clean-up tests data
        """
        project = self.datatypeFactory.get_project()
        FilesHelper().remove_project_structure(project.name)
        
        # Remove EXPORT folder
        export_folder = os.path.join(cfg.TVB_STORAGE, ExportManager.EXPORT_FOLDER_NAME)
        if os.path.exists(export_folder):
            shutil.rmtree(export_folder)
        
              
    def test_get_exporters_for_data(self):
        """
        Test retrieval of exporters that can be used for a given data.
        """
        datatype = self.datatypeFactory.create_simple_datatype()       
        exporters = self.export_manager.get_exporters_for_data(datatype)
        
        # Only TVB export can export any type of data type
        self.assertEqual(1, len(exporters), "Incorrect number of exporters.")
        
        
    def test_get_exporters_for_data_with_no_data(self):
        """
        Test retrieval of exporters when data == None.
        """        
        self.assertRaises(InvalidExportDataException, self.export_manager.get_exporters_for_data, None)
        
    
    def test_tvb_export_of_simple_datatype(self):
        """
            Test export of a data type which has no data stored on file system
        """
        datatype = self.datatypeFactory.create_simple_datatype()       
        file_name, file_path, _ = self.export_manager.export_data(datatype, self.TVB_EXPORTER, 
                                                    self.project)
        
        self.assertTrue(file_name is not None, "Export process should return a file name")
        self.assertTrue(file_path is not None, "Export process should return path to export file")
        
        self.assertTrue(os.path.exists(file_path), "Could not find export file: %s on disk."%file_path)

    def test_tvb_export_of_datatype_with_storage(self):
        """
            Test export of a data type which has no data stored on file system
        """
        datatype = self.datatypeFactory.create_datatype_with_storage()       
        file_name, file_path, _ = self.export_manager.export_data(datatype, self.TVB_EXPORTER, 
                                                    self.project)
        
        self.assertTrue(file_name is not None, "Export process should return a file name")
        self.assertTrue(file_path is not None, "Export process should return path to export file")
        
        self.assertTrue(os.path.exists(file_path), "Could not find export file: %s on disk."%file_path)
    
    def test_tvb_export_for_datatype_group(self):
        """
            This method checks export of a data type group
        """
        datatype_group = self.datatypeFactory.create_datatype_group()       
        file_name, file_path, _ = self.export_manager.export_data(datatype_group, self.TVB_EXPORTER, 
                                                    self.project)
        
        self.assertTrue(file_name is not None, "Export process should return a file name")
        self.assertTrue(file_path is not None, "Export process should return path to export file")
        
        self.assertTrue(os.path.exists(file_path), "Could not find export file: %s on disk."%file_path)
        
        # Now check if the generated file is a correct ZIP file
        self.assertTrue(zipfile.is_zipfile(file_path), "Generated file is not a valid ZIP file")
        
        with closing(zipfile.ZipFile(file_path)) as zip_file:
            list_of_files = zip_file.namelist()
    
            count_datatypes = dao.count_datatypes_in_group(datatype_group.id)
            
            # Check if ZIP files contains files for data types + operation
            self.assertEqual(count_datatypes * 2, len(list_of_files), 
                             "Should have 2 x nr datatypes files, one for operations one for datatypes")

        
    def test_export_with_invalid_data(self):
        """
            Test scenarios when data provided to export method is invalid
        """
        # Test with no datatype
        self.assertRaises(InvalidExportDataException, self.export_manager.export_data, 
                          None, self.TVB_EXPORTER, self.project)
        
        # Test with no exporter 
        datatype = self.datatypeFactory.create_datatype_with_storage()  
        self.assertRaises(ExportException, self.export_manager.export_data, 
                          datatype, None, self.project)
        
        # test with wrong exporter
        self.assertRaises(ExportException, self.export_manager.export_data, 
                          datatype, "wrong_exporter", self.project)
        
        # test with no project folder
        self.assertRaises(ExportException, self.export_manager.export_data, 
                          datatype, self.TVB_EXPORTER, None)
    
    def test_export_project_failure(self):
        """
            This method tests export of project with None data
        """
        self.assertRaises(ExportException, self.export_manager.export_project, None)
        
    def tet_export_project(self):
        """
            Test export of a project
        """
        project = self.datatypeFactory.get_project()
        export_file = self.export_manager.export_project(project)
        
        self.assertTrue(export_file is not None, "Export process should return path to export file")
        self.assertTrue(os.path.exists(export_file), "Could not find export file: %s on disk."%export_file)
        
        # Now check if the generated file is a correct ZIP file
        self.assertTrue(zipfile.is_zipfile(export_file), "Generated file is not a valid ZIP file")
        
            
def suite():
    """ 
        Gather all the tests in a test suite.
    """
    test_suite = unittest.TestSuite()
    test_suite.addTest(unittest.makeSuite(ExportersTest))
    return test_suite

if __name__ == "__main__":
    #So you can run tests from this package individually.
    unittest.main()
