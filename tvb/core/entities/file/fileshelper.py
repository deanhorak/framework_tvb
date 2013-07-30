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
.. moduleauthor:: Calin Pavel <calin.pavel@codemart.ro>
.. moduleauthor:: Lia Domide <lia.domide@codemart.ro>
"""

import os
import shutil
import json
import zipfile
from contextlib import closing
from zipfile import ZipFile, ZIP_DEFLATED, BadZipfile
from tvb.basic.config.settings import TVBSettings
from tvb.basic.logger.builder import get_logger
from tvb.core.utils import synchronized
from tvb.core.entities.transient.structure_entities import DataTypeMetaData, GenericMetaData
from tvb.core.entities.file.metadatahandler import XMLReader, XMLWriter
from tvb.core.entities.file.exceptions import FileStructureException


from threading import Lock
LOCK_CREATE_FOLDER = Lock()


class FilesHelper():
    """
    This class manages all Structure related operations, using File storage.
    It will handle creating meaning-full entities and retrieving existent ones. 
    """
    TEMP_FOLDER = "TEMP"
    IMAGES_FOLDER = "IMAGES"
    PROJECTS_FOLDER = "PROJECTS"

    TVB_FILE_EXTENSION = XMLWriter.FILE_EXTENSION    
    TVB_STORAGE_FILE_EXTENSION = ".h5"

    TVB_PROJECT_FILE = "Project" + TVB_FILE_EXTENSION
    TVB_OPERARATION_FILE = "Operation" + TVB_FILE_EXTENSION
    
    def __init__(self):
        self.logger = get_logger(self.__class__.__module__)
    
    
    ############# PROJECT RELATED methods ##################################
    
    @synchronized(LOCK_CREATE_FOLDER)
    def check_created(self, path = TVBSettings.TVB_STORAGE):
        """
        Check that the given folder exists, otherwise create it, with the entire tree of parent folders.
        This method is synchronized, for parallel access from events, to avoid conflicts.
        """
        try:
            if not os.path.exists(path):
                self.logger.debug("Creating folder:" + str(path))
                os.makedirs(path, mode=TVBSettings.ACCESS_MODE_TVB_FILES)
                os.chmod(path, TVBSettings.ACCESS_MODE_TVB_FILES)
        except OSError, excep:
            self.logger.error("COULD NOT CREATE FOLDER! CHECK ACCESS ON IT!")
            self.logger.exception(excep)
            raise FileStructureException("Could not create Folder"+ str(path))
    
        
    def get_project_folder(self, project, *sub_folders):
        """
        Retrieve the root path for the given project. 
        If root folder is not created yet, will create it.
        """
        if hasattr(project, 'name'):
            project = project.name
        complete_path = os.path.join(TVBSettings.TVB_STORAGE, self.PROJECTS_FOLDER, project)
        if sub_folders is not None:
            complete_path = os.path.join(complete_path, *sub_folders)
        if not os.path.exists(complete_path):
            self.check_created(complete_path)
        return complete_path
    
    def rename_project_structure(self, project_name, new_name):
        """ Rename Project folder or THROW FileStructureException. """
        try:     
            path = self.get_project_folder(project_name)     
            folder = os.path.split(path)[0]
            new_full_name = os.path.join(folder, new_name)            
        except Exception, excep:
            self.logger.error("Could not rename node!")
            self.logger.exception(excep)
            raise FileStructureException("Could not Rename:"+ str(new_name))
        if os.path.exists(new_full_name):
            raise FileStructureException("File already used "+ str(new_name) + " Can not add a duplicate!")
        try:
            os.rename(path, new_full_name)
            return path , new_full_name
        except Exception, excep:
            self.logger.error("Could not rename node!")
            self.logger.exception(excep)
            raise FileStructureException("Could not Rename: "+ str(new_name))
    
    
    def remove_project_structure(self, project_name):
        """ Remove all folders for project or THROW FileStructureException. """
        try:
            complete_path = self.get_project_folder(project_name)
            if os.path.exists(complete_path):
                if os.path.isdir(complete_path):
                    shutil.rmtree(complete_path)
                else:
                    os.remove(complete_path)
            self.logger.debug("Project folders were removed for "+ project_name)
        except OSError, excep:
            self.logger.error("A problem occurred while removing folder.")
            self.logger.exception(excep)
            raise FileStructureException("Permission denied. Make sure you have write access on TVB folder!")
     
     
    def get_project_meta_file_path(self, project_name):
        """
        Retrieve project meta info file path.
        
        :returns: File path for storing Project meta-data
            File might not exist yet, but parent folder is created after this method call.
            
        """
        complete_path = self.get_project_folder(project_name)
        complete_path = os.path.join(complete_path, self.TVB_PROJECT_FILE)
        return complete_path
    
    
    def write_project_metadata(self, project):
        """
        :param new_meta_data: GenericMetaData instance
        """
        proj_path = self.get_project_meta_file_path(project.name)
        _, meta_dictionary = project.to_dict()
        meta_entity = GenericMetaData(meta_dictionary)
        XMLWriter(meta_entity).write(proj_path)
        os.chmod(proj_path, TVBSettings.ACCESS_MODE_TVB_FILES)
        
     
    ############# OPERATION related METHODS Start Here #########################
    def get_operation_folder(self, project_name, operation_id):
        """
        Computes the folder where operation details are stored
        """
        operation_path = self.get_project_folder(project_name, str(operation_id))
        if not os.path.exists(operation_path):
            self.check_created(operation_path)
        return operation_path
    
    def get_operation_meta_file_path(self, project_name, operation_id):
        """
        Retrieve the path to operation meta file
        
        :param project_name: name of the current project.
        :param operation_id: Identifier of Operation in given project
        :returns: File path for storing Operation meta-data. File might not be yet created,
            but parent folder exists after this method.
             
        """
        complete_path = self.get_operation_folder(project_name, operation_id)
        complete_path = os.path.join(complete_path, self.TVB_OPERARATION_FILE)
        return complete_path
    
    
    def write_operation_metadata(self, operation):
        """
        :param operation: DB stored operation instance.
        """
        project_name = operation.project.name
        op_path = self.get_operation_meta_file_path(project_name, operation.id)
        _, equivalent_dict = operation.to_dict()
        meta_entity = GenericMetaData(equivalent_dict)
        XMLWriter(meta_entity).write(op_path)
        os.chmod(op_path, TVBSettings.ACCESS_MODE_TVB_FILES)
        
        
    def update_operation_metadata(self, project_name, new_group_name, operation_id, is_group=False):
        """
        Update operation meta data.
        :param is_group: when FALSE, use parameter 'new_group_name' for direct assignment on operation.user_group
        when TRUE, update  operation.operation_group.name = parameter 'new_group_name'
        """
        op_path = self.get_operation_meta_file_path(project_name, operation_id)
        if not os.path.exists(op_path):
            self.logger.warning("Trying to update an operation-meta file which does not exist."
                                " It could happen in a group where partial entities have errors!")
            return
        op_meta_data = XMLReader(op_path).read_metadata()

        if is_group:
            group_meta_str = op_meta_data[DataTypeMetaData.KEY_FK_OPERATION_GROUP]
            group_meta = json.loads(group_meta_str)
            group_meta[DataTypeMetaData.KEY_OPERATION_GROUP_NAME] = new_group_name
            op_meta_data[DataTypeMetaData.KEY_FK_OPERATION_GROUP] = json.dumps(group_meta)
        else:
            op_meta_data[DataTypeMetaData.KEY_OPERATION_TAG] = new_group_name
        XMLWriter(op_meta_data).write(op_path)


    def remove_operation_data(self, project_name, operation_id):  
        """
        Remove H5 storage fully.
        """
        try:
            complete_path = self.get_operation_folder(project_name, operation_id)
            if os.path.isdir(complete_path):
                shutil.rmtree(complete_path)
            else:
                os.remove(complete_path)
        except Exception, excep:
            self.logger.error(excep)
            raise FileStructureException("Could not remove files for OP" + str(operation_id))
    
    ####################### DATA-TYPES METHODS Start Here #####################
     
    def remove_datatype(self, datatype):  
        """
        Remove H5 storage fully.
        """
        try:
            os.remove(datatype.get_storage_file_path())
        except Exception, excep:
            self.logger.error(excep)
            raise FileStructureException("Could not remove " + str(datatype))
            
            
    def move_datatype(self, datatype, new_project_name, new_op_id):
        """
        Move H5 storage into a new location
        """
        try:
            full_path = datatype.get_storage_file_path()
            folder = self.get_project_folder(new_project_name, str(new_op_id))
            full_new_file = os.path.join(folder, os.path.split(full_path)[1])
            os.rename(full_path, full_new_file)
        except Exception, excep:
            self.logger.error(excep)
            raise FileStructureException("Could not move " + str(datatype))
    
    
    ######################## IMAGES METHODS Start Here #######################    
    def get_images_folder(self, project_name, operation_id):
        """
        Computes the name/path of the folder where to store images.
        """
        operation_folder = self.get_operation_folder(project_name, operation_id)
        images_folder = os.path.join(operation_folder, self.IMAGES_FOLDER)
        if not os.path.exists(images_folder):
            self.check_created(images_folder)
        return images_folder
        
    def write_image_metadata(self, figure):
        """
        Writes figure meta-data into XML file
        """
        _, dict_data = figure.to_dict()
        meta_entity = GenericMetaData(dict_data)
        XMLWriter(meta_entity).write(self._compute_image_metadata_file(figure))
        
    def remove_image_metadata(self, figure):
        """
        Remove the file storing image meta data
        """
        metadata_file = self._compute_image_metadata_file(figure)
        if os.path.exists(metadata_file):
            os.remove(metadata_file)
        
    def _compute_image_metadata_file(self, figure):
        """
        Computes full path of image meta data XML file. 
        """
        name = figure.file_path.split('.')[0]
        images_folder = self.get_images_folder(figure.project.name, figure.operation.id)
        return os.path.join(TVBSettings.TVB_STORAGE, images_folder, name + XMLWriter.FILE_EXTENSION)
    
    
    @staticmethod
    def find_relative_path(full_path, root_path = TVBSettings.TVB_STORAGE):
        """
        :param full_path: Absolute full path
        :root_path: find relative path from param full_path to this root.
        """
        try:
            full =  os.path.normpath(full_path)
            prefix = os.path.normpath(root_path)
            result = full.replace(prefix, '')
            #  Make sure the resulting relative path doesn't start with root, 
            # to be then treated as an absolute path.      
            if result.startswith(os.path.sep):
                result = result.replace(os.path.sep, '', 1)
            return result
        except Exception, excep:
            logger = get_logger(__name__)
            logger.warning("Could not normalize "+ str(full_path))
            logger.warning(str(excep))
            return full_path  
            
            
    ######################## GENERIC METHODS Start Here #######################
        
    @staticmethod
    def parse_xml_content(xml_content):
        """
        Delegate reading of some XML content.
        Will parse the XMl and return a dictionary of elements with max 2 levels.
        """
        return XMLReader(None).parse_xml_content_to_dict(xml_content)
    
    
    @staticmethod
    def zip_files(zip_full_path, files):
        """
        This method creates a ZIP file with all files provided as parameters
        :param zip_full_path: full path and name of the result ZIP file
        :param files: array with the FULL names/path of the files to add into ZIP 
        """
        with closing(ZipFile(zip_full_path, "w", ZIP_DEFLATED, True)) as zip_file:
            for file_to_include in files:
                zip_file.write(file_to_include, os.path.basename(file_to_include))
    
    @staticmethod
    def zip_folders(zip_full_path, folders, folder_prefix = None):
        """
        This method creates a ZIP file with all folders provided as parameters
        :param zip_full_path: full path and name of the result ZIP file
        :param folders: array with the FULL names/path of the folders to add into ZIP 
        """
        with closing(ZipFile(zip_full_path, "w", ZIP_DEFLATED, True)) as zip_res:
            for folder in set(folders):
                parent_folder, _ = os.path.split(folder)
                for root, _, files in os.walk(folder):
                    #NOTE: ignore empty directories
                    for file_n in files:
                        abs_file_n = os.path.join(root, file_n)
                        zip_file_n = abs_file_n[len(parent_folder) + len(os.sep):]
                        if folder_prefix is not None:
                            zip_file_n = folder_prefix + zip_file_n
                        zip_res.write(abs_file_n, zip_file_n)
                        
    
    @staticmethod
    def zip_folder(result_name, folder_root):
        """
        Given a folder and a ZIP result name, create the corresponding archive.
        """
        with closing(ZipFile(result_name, "w", ZIP_DEFLATED, True)) as zip_res:
            for root, _, files in os.walk(folder_root):
                #NOTE: ignore empty directories
                for file_n in files:
                    abs_file_n = os.path.join(root, file_n)
                    zip_file_n = abs_file_n[len(folder_root) + len(os.sep):]
                    zip_res.write(abs_file_n, zip_file_n)
                    
        return result_name
     
     
    def unpack_zip(self, uploaded_zip, folder_path):
        """ Simple method to unpack ZIP archive in a given folder. """
        try:
            zip_arch = zipfile.ZipFile(uploaded_zip)
            result = []
            for filename in zip_arch.namelist():
                new_file_name = os.path.join(folder_path, filename)
                src = zip_arch.open(filename, 'rU')
                if new_file_name.endswith('/'):
                    os.makedirs(new_file_name)
                else:
                    FilesHelper.copy_file(src, new_file_name)
                result.append(new_file_name)
            return result
        except BadZipfile, excep:
            self.logger.error(excep)
            raise FileStructureException("Invalid ZIP file...")
        except Exception, excep:
            self.logger.error(excep)
            raise FileStructureException("Could not unpack the given ZIP file...")
            

    @staticmethod
    def copy_file(source, dest, dest_postfix=None, buffer_size = 1024*1024):
        """
        Copy a file from source to dest. source and dest can either be strings or 
        any object with a read or write method, like StringIO for example.
        """
        if not hasattr(source, 'read'):
            source = open(source, 'rb')
        if not hasattr(dest, 'write'):
            if dest_postfix is not None:
                dest = os.path.join(dest, dest_postfix)
            if not os.path.exists(os.path.dirname(dest)):
                os.makedirs(os.path.dirname(dest))
            dest = open(dest, 'wb')
        while 1:
            copy_buffer = source.read(buffer_size)
            if copy_buffer:
                dest.write(copy_buffer)
            else:
                break
        source.close()
        dest.close()
  
  
    @staticmethod
    def remove_files(file_list, ignore_exception=False):
        """
        :param file_list: list of file paths to be removed.
        :param ignore_exception: When True and one of the specified files could not be removed, an exception is raised.  
        """
        for file_ in file_list:
            try:
                if os.path.isfile(file_):
                    os.remove(file_)
                if os.path.isdir(file_):
                    shutil.rmtree(file_)
            except Exception, exc:
                logger = get_logger(__name__)
                logger.error("Could not remove " + str(file_))
                logger.exception(exc)
                if not ignore_exception:
                    raise exc   
        
        
    @staticmethod
    def remove_folder(folder_path, ignore_errors=False):
        """
        Given a folder path, try to remove that folder from disk.
        :param ignore_errors: When False, and given folder does not exist or is not folder, throw FileStructureException. 
        """
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            shutil.rmtree(folder_path, ignore_errors)
            return 
        if not ignore_errors:
            raise FileStructureException("Given path does not exists, or is not a folder "+ str(folder_path))
        
     
    @staticmethod
    def compute_size_on_disk(file_path):
        """
        Given a file's path, return size occupied on disk by that file.
        Size should be a number, representing size in KB.
        """
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return int(os.path.getsize(file_path) / 1024)
        return 0
        
        
        