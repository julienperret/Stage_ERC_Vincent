
scalaVersion := "2.12.6"

libraryDependencies += "com.github.pathikrit" %% "better-files" % "3.6.0"

initialCommands in console := """
    |import better.files._
    |import File._
    |import better.files.Dsl.SymbolicOperations
    |import better.files.Dsl._
    |""".stripMargin

