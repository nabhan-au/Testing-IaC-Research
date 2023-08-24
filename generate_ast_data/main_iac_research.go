package main

import (
	"encoding/csv"
	"errors"
	"flag"
	"fmt"
	"go/ast"
	"go/build"
	"go/importer"
	"go/parser"
	"go/token"
	"go/types"
	"os"
	"path"
	"path/filepath"
	"strconv"
	"strings"
)

type v struct {
	info           *types.Info
	outputfileName string
	packageName    string
	testFileName   string
}

func (v v) Visit(node ast.Node) (w ast.Visitor) {
	switch node := node.(type) {
	case *ast.FuncDecl:
		tempNode := (*node)
		funcDeclName := tempNode.Name.Name
		pos := tempNode.Pos()
		ast.Inspect(node, func(n ast.Node) bool {
			switch body := n.(type) {
			case *ast.CallExpr:
				writed := false
				switch fun := body.Fun.(type) {
				case *ast.SelectorExpr:
					if pkgID, ok := fun.X.(*ast.Ident); ok {
						funcName := fun.Sel.Name
						if v.info.Uses[pkgID] == nil {
							return true
						}
						switch selectExpr := v.info.Uses[pkgID].(type) {
						case *types.PkgName:
							modulePath := selectExpr.Imported().Path()
							containTerratest := isTerratestModule(modulePath)
							v.writeFile(funcName, funcDeclName, containTerratest, modulePath, "funcDecl", int(pos))
							writed = true
						case *types.Var:
							switch typ := selectExpr.Type().(type) {
							case *types.Named:
								pack := typ.Obj().Pkg()
								if pack != nil {
									modulePath := pack.Path()
									containTerratest := isTerratestModule(modulePath)
									v.writeFile(funcName, funcDeclName, containTerratest, modulePath, "funcDecl", int(pos))
									writed = true
								}
							case *types.Pointer:
								switch typ := typ.Elem().(type) {
								case *types.Named:
									pack := typ.Obj().Pkg()
									if pack != nil {
										modulePath := pack.Path()
										containTerratest := isTerratestModule(modulePath)
										v.writeFile(funcName, funcDeclName, containTerratest, modulePath, "funcDecl", int(pos))
										writed = true
									}
								}
							}
						}

					}
					if fun.Sel != nil && !writed {
						funcName := fun.Sel.Name
						if v.info.Uses[fun.Sel] == nil {
							return true
						}
						pack := v.info.Uses[fun.Sel].Pkg()
						if pack != nil {
							modulePath := v.info.Uses[fun.Sel].Pkg().Path()
							containTerratest := isTerratestModule(modulePath)
							v.writeFile(funcName, funcDeclName, containTerratest, modulePath, "funcDecl", int(pos))
						}
					}

				case *ast.Ident:
					pkgID := fun
					funcName := fun.Name
					if v.info.Uses[pkgID] == nil {
						return true
					}
					pack := v.info.Uses[pkgID].Pkg()
					if pack != nil {
						modulePath := v.info.Uses[pkgID].Pkg().Path()
						containTerratest := isTerratestModule(modulePath)
						v.writeFile(funcName, funcDeclName, containTerratest, modulePath, "funcDecl", int(pos))
					}
				}
			}
			return true
		})
	case *ast.CallExpr:
		switch fun := node.Fun.(type) {
		case *ast.SelectorExpr:
			funcDeclName := fun.Sel.Name
			pos := fun.Pos()
			if funcDeclName != "Describe" {
				return v
			}
			for _, arg := range node.Args {
				ast.Inspect(arg, func(n ast.Node) bool {
					switch body := n.(type) {
					case *ast.CallExpr:
						writed := false
						switch fun := body.Fun.(type) {
						case *ast.SelectorExpr:
							if pkgID, ok := fun.X.(*ast.Ident); ok {
								funcName := fun.Sel.Name
								if v.info.Uses[pkgID] == nil {
									return true
								}
								switch selectExpr := v.info.Uses[pkgID].(type) {
								case *types.PkgName:
									modulePath := selectExpr.Imported().Path()
									containTerratest := isTerratestModule(modulePath)
									v.writeFile(funcName, funcDeclName, containTerratest, modulePath, "funcDecl", int(pos))
									writed = true
								case *types.Var:
									switch typ := selectExpr.Type().(type) {
									case *types.Named:
										pack := typ.Obj().Pkg()
										if pack != nil {
											modulePath := pack.Path()
											containTerratest := isTerratestModule(modulePath)
											v.writeFile(funcName, funcDeclName, containTerratest, modulePath, "funcDecl", int(pos))
											writed = true
										}
									case *types.Pointer:
										switch typ := typ.Elem().(type) {
										case *types.Named:
											pack := typ.Obj().Pkg()
											if pack != nil {
												modulePath := pack.Path()
												containTerratest := isTerratestModule(modulePath)
												v.writeFile(funcName, funcDeclName, containTerratest, modulePath, "funcDecl", int(pos))
												writed = true
											}
										}
									}
								}

							}
							if fun.Sel != nil && !writed {
								funcName := fun.Sel.Name
								if v.info.Uses[fun.Sel] == nil {
									return true
								}
								pack := v.info.Uses[fun.Sel].Pkg()
								if pack != nil {
									modulePath := v.info.Uses[fun.Sel].Pkg().Path()
									containTerratest := isTerratestModule(modulePath)
									v.writeFile(funcName, funcDeclName, containTerratest, modulePath, "funcDecl", int(pos))
								}
							}

						case *ast.Ident:
							pkgID := fun
							funcName := fun.Name
							if v.info.Uses[pkgID] == nil {
								return true
							}
							pack := v.info.Uses[pkgID].Pkg()
							if pack != nil {
								modulePath := v.info.Uses[pkgID].Pkg().Path()
								containTerratest := isTerratestModule(modulePath)
								v.writeFile(funcName, funcDeclName, containTerratest, modulePath, "funcDecl", int(pos))
							}
						}
					}
					return true
				})

			}
		}
	}
	return v
}

func (v v) writeFile(funcName string, funcDeclName string, containTerratest bool, modulePath string, funcType string, pos int) error {
	header := []string{"file_name", "package_name", "func_decl_name", "func_name", "module_path", "contain_terratest", "func_type", "pos"}
	f, err := os.OpenFile(v.outputfileName, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	defer f.Close()

	if err != nil {
		return err
	}

	w := csv.NewWriter(f)
	defer w.Flush()

	if fi, err := f.Stat(); (err == nil) && (fi.Size() == 0) {
		if err := w.Write(header); err != nil {
			return err
		}
	}
	splitFileName := strings.Split(v.testFileName, "clone_repo/")
	row := []string{splitFileName[len(splitFileName)-1], v.packageName, funcDeclName, funcName, modulePath, strconv.FormatBool(containTerratest), funcType, strconv.FormatInt(int64(pos), 10)}
	if err := w.Write(row); err != nil {
		return err
	}
	return nil
}

func isTerratestModule(module string) bool {
	return strings.Contains(module, "github.com/gruntwork-io/terratest/modules")
}

func checkTestCases(filepath string, outputPath string, fset *token.FileSet, directoryPath string, errorOutput string) error {
	buildPkg, err := build.ImportDir(filepath, build.ImportMode(0))
	if err != nil {
		return err
	}

	filepathMap := map[string][]string{}
	packageMap := map[string][]*ast.File{}
	for _, filename := range buildPkg.GoFiles {
		if filename == "main_iac_research.go" {
			continue
		}
		file, err := parser.ParseFile(fset, path.Join(filepath, filename), nil, parser.AllErrors)
		noGoError := &build.NoGoError{}
		if errors.As(err, &noGoError) {
			return nil
		}

		if err != nil {
			return err
		}
		packageMap[file.Name.Name] = append(packageMap[file.Name.Name], file)
		filepathMap[file.Name.Name] = append(filepathMap[file.Name.Name], path.Join(filepath, filename))
	}

	for _, filename := range buildPkg.CgoFiles {
		file, err := parser.ParseFile(fset, path.Join(filepath, filename), nil, parser.AllErrors)
		noGoError := &build.NoGoError{}
		if errors.As(err, &noGoError) {
			return nil
		}

		if err != nil {
			return err
		}
		packageMap[file.Name.Name] = append(packageMap[file.Name.Name], file)
		filepathMap[file.Name.Name] = append(filepathMap[file.Name.Name], path.Join(filepath, filename))
	}

	for _, filename := range buildPkg.TestGoFiles {
		file, err := parser.ParseFile(fset, path.Join(filepath, filename), nil, parser.AllErrors)
		noGoError := &build.NoGoError{}
		if errors.As(err, &noGoError) {
			return nil
		}

		if err != nil {
			return err
		}
		packageMap[file.Name.Name] = append(packageMap[file.Name.Name], file)
		filepathMap[file.Name.Name] = append(filepathMap[file.Name.Name], path.Join(filepath, filename))
	}

	for _, filename := range buildPkg.XTestGoFiles {
		file, err := parser.ParseFile(fset, path.Join(filepath, filename), nil, parser.AllErrors)
		noGoError := &build.NoGoError{}
		if errors.As(err, &noGoError) {
			return nil
		}

		if err != nil {
			return err
		}
		packageMap[file.Name.Name] = append(packageMap[file.Name.Name], file)
		filepathMap[file.Name.Name] = append(filepathMap[file.Name.Name], path.Join(filepath, filename))
	}
	for _, filename := range buildPkg.IgnoredGoFiles {
		file, err := parser.ParseFile(fset, path.Join(filepath, filename), nil, parser.AllErrors)
		noGoError := &build.NoGoError{}
		if errors.As(err, &noGoError) {
			return nil
		}

		if err != nil {
			return err
		}
		packageMap[file.Name.Name] = append(packageMap[file.Name.Name], file)
		filepathMap[file.Name.Name] = append(filepathMap[file.Name.Name], path.Join(filepath, filename))
	}

	for key, astFiles := range packageMap {
		conf := types.Config{Importer: importer.For("source", nil)}
		info := &types.Info{
			Uses: make(map[*ast.Ident]types.Object),
		}

		if _, err = conf.Check(key, fset, astFiles, info); err != nil {
			fmt.Println(info)
			fmt.Println(err)
			writeErrorPackageToCSV(filepath, directoryPath, err, errorOutput)
		}

		for index, file := range astFiles {
			ast.Walk(v{info, outputPath, key, filepathMap[key][index]}, file)
		}
	}
	return nil
}

func getAllDirectoryFromPathThatContainGoFile(packagePath string) ([]string, error) {
	firstPath := packagePath
	var directories []string
	var excludeDirectories []string
	err := filepath.Walk(packagePath, func(path string, info os.FileInfo, err error) error {
		if info.IsDir() {
			containExcludeDirectories := checkIfFilePathMatchPathList(path, excludeDirectories)
			if containExcludeDirectories {
				return nil
			}
			if path != firstPath {
				if _, err := os.Stat(path + "/go.mod"); err == nil {
					excludeDirectories = append(excludeDirectories, path)
				}
			}
			files, err := WalkMatch(path, "*.go")
			if err != nil {
				return err
			}
			if len(files) > 0 && !containExcludeDirectories {
				directories = append(directories, path)
			}
		}
		return nil
	})
	if err != nil {
		return []string{}, err
	}
	return directories, nil
}

func WalkMatch(root, pattern string) ([]string, error) {
	var matches []string
	err := filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if info.IsDir() {
			return nil
		}
		if matched, err := filepath.Match(pattern, filepath.Base(path)); err != nil {
			return err
		} else if matched {
			matches = append(matches, path)
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
	return matches, nil
}

func checkIfFilePathMatchPathList(path string, pathList []string) bool {
	for _, p := range pathList {
		if strings.Contains(path, p) || path == p {
			return true
		}
	}
	return false
}

func writeErrorPackageToCSV(packageName string, packagePath string, error_message error, errorOutput string) error {
	header := []string{"package_name", "package_path", "error_message"}
	f, err := os.OpenFile(errorOutput, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	defer f.Close()

	if err != nil {
		return err
	}

	w := csv.NewWriter(f)
	defer w.Flush()

	if fi, err := f.Stat(); (err == nil) && (fi.Size() == 0) {
		if err := w.Write(header); err != nil {
			return err
		}
	}

	row := []string{packageName, packagePath, error_message.Error()}
	if err := w.Write(row); err != nil {
		return err
	}
	return nil
}

func main() {
	directoryPathFlag := flag.String("directoryPath", "", "path to directory")
	outputPathFlag := flag.String("outputPath", "", "path to output file")
	flag.Parse()
	directoryPath := string(*directoryPathFlag)
	outputPath := string(*outputPathFlag)
	outputFileName := strings.Join(strings.Split(strings.Split(directoryPath, "clone_repo/")[1], "/"), "_") + ".csv"
	errorFileName := strings.Join(strings.Split(strings.Split(directoryPath, "clone_repo/")[1], "/"), "_") + "_error.csv"
	output := outputPath + "/" + outputFileName
	errorOutput := outputPath + "/" + errorFileName
	directories, err := getAllDirectoryFromPathThatContainGoFile(directoryPath)
	if err != nil {
		fmt.Println(err)
	}
	fset := token.NewFileSet()
	for _, directory := range directories {
		err := checkTestCases(directory, output, fset, directoryPath, errorOutput)
		if err != nil {
			writeErrorPackageToCSV(directory, directoryPath, err, errorOutput)
			fmt.Println(err)
		}
	}
}
