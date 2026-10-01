from setuptools import setup
setup(name='hcr_sorting', version='0.1.0', packages=['hcr_sorting'],
      data_files=[('share/ament_index/resource_index/packages',['resource/hcr_sorting']),
                  ('share/hcr_sorting',['package.xml'])],
      install_requires=['setuptools'], zip_safe=True,
      entry_points={'console_scripts':['sorter_node = hcr_sorting.node:main',
                                       'mock_hcr = hcr_sorting.mock_hcr:main',
                                       'dummy_control = hcr_sorting.dummy_control:main']})
